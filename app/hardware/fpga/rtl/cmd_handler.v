// cmd_handler.v
// Decides what to do with each command frame and answers with an ACK.
// It follows app/backend/runtime/sim_controller.py, the software stand-in
// the backend is tested against.
//
// Commands handled here:
//   0x02 OPEN_SESSION   0x10 LOAD_PLAN   0x11 COMMIT_PLAN
//   0x12 ARM   0x13 START   0x14 ABORT   0x15 CLEAR
//   0x16 SET_TRIP_DAYS  (proposed extension, see docs/SHUTTLE_CCS_EXTENSION.md:
//        mission_id(4) trip_days(4); allowed in LOADED or ARMED; 1..9999 days)
// (DISCOVER and GET_STATUS are answered by status_gen, not here.)
//
// Checks, in this order:
//   1. Session. Commands must carry the active session id.   -> BAD_SESSION
//   2. Sequence number.
//        same as last and same bytes  -> send the saved ACK again, do nothing
//        same as last, other bytes    -> SEQ_CONFLICT
//        lower than last, or zero     -> STALE_SEQ
//   3. Is the command allowed now?  -> BAD_STATE / BAD_MISSION / BAD_PLAN /
//                                      BAD_PLAN_CRC
//   4. Apply it (one-clock do_* pulse to the sequencer) and remember the
//      command and its ACK for step 2.
//   Steps 1 and 2 failing do not use up the sequence number. Step 3
//   failing does.
//
// LOAD_PLAN only stages a plan here. COMMIT_PLAN hands it to the sequencer.
//
// ACK payload (16 bytes): original_type(1) result(1) detail(2)
//   mission_id(4) applied_tick(4) plan_crc16(2) 0(2)
// plan_crc16 in an ACK = CRC of the active plan, else of the staged plan,
// else 0. This matches every golden ACK frame.

module cmd_handler (
    input  wire         clk,
    input  wire         rst_n,

    // good frame from frame_rx
    input  wire         frame_valid,
    input  wire [7:0]   frame_type,
    input  wire [15:0]  frame_seq,
    input  wire [31:0]  frame_session,
    input  wire [223:0] frame_payload,

    // mission status from the sequencer
    input  wire [2:0]   state,
    input  wire         plan_valid,
    input  wire [31:0]  plan_mission_id,
    input  wire [15:0]  plan_crc16,
    input  wire [31:0]  tick_count,

    // checked commands to the sequencer (one-clock pulses)
    output reg          do_commit,
    output reg          do_arm,
    output reg          do_start,
    output reg          do_abort,
    output reg          do_clear,
    output reg          do_set_days,        // SET_TRIP_DAYS accepted
    output wire [31:0]  set_days_value,

    // staged plan (used by the sequencer on do_commit)
    output wire [31:0]  staged_mission_id,
    output wire [31:0]  staged_departure_tick,
    output wire [31:0]  staged_arrival_tick,
    output wire [31:0]  staged_end_tick,
    output wire [31:0]  staged_initial_fuel_g,
    output wire [31:0]  staged_departure_fuel_g,
    output wire [31:0]  staged_capture_fuel_g,
    output reg  [15:0]  staged_crc16,

    output reg  [31:0]  session,            // active session, 0 = none

    // ACK frame to frame_tx
    input  wire         tx_free,
    output reg          ack_start,
    output wire [7:0]   ack_type,
    output wire [15:0]  ack_seq,
    output wire [319:0] ack_payload,
    output wire [7:0]   ack_len,
    output wire         ack_pending         // an ACK is being prepared or waiting
);

    // Message types.
    localparam [7:0] T_OPEN_SESSION = 8'h02,
                     T_LOAD_PLAN    = 8'h10,
                     T_COMMIT_PLAN  = 8'h11,
                     T_ARM          = 8'h12,
                     T_START        = 8'h13,
                     T_ABORT        = 8'h14,
                     T_CLEAR        = 8'h15,
                     T_SET_TRIP_DAYS = 8'h16;

    // Mission states.
    localparam [2:0] ST_IDLE    = 3'd0,
                     ST_LOADED  = 3'd1,
                     ST_ARMED   = 3'd2,
                     ST_RUNNING = 3'd3,
                     ST_SAFE    = 3'd4;

    // ACK detail codes.
    localparam [3:0] D_OK           = 4'd0,
                     D_BAD_STATE    = 4'd1,
                     D_BAD_MISSION  = 4'd2,
                     D_BAD_SESSION  = 4'd3,
                     D_BAD_PLAN     = 4'd4,
                     D_BAD_PLAN_CRC = 4'd5,
                     D_SEQ_CONFLICT = 4'd6,
                     D_STALE_SEQ    = 4'd7;

    localparam [31:0] MAX_END_TICK = 32'd360000;

    // Handler steps.
    localparam [1:0] S_IDLE   = 2'd0,   // wait for a command frame
                     S_CRC    = 2'd1,   // LOAD_PLAN only: CRC over the 28 plan bytes
                     S_DECIDE = 2'd2,   // run the checks, apply
                     S_ACK    = 2'd3;   // hand the ACK to the transmitter

    reg [1:0] step;

    // The command being handled.
    reg [7:0]   f_type;
    reg [15:0]  f_seq;
    reg [31:0]  f_session;
    reg [223:0] f_payload;

    // Staged plan (the 28 LOAD_PLAN bytes as received).
    reg         staged_valid;
    reg [223:0] staged;

    assign staged_mission_id       = staged[31:0];
    assign staged_departure_tick   = staged[63:32];
    assign staged_arrival_tick     = staged[95:64];
    assign staged_end_tick         = staged[127:96];
    assign staged_initial_fuel_g   = staged[159:128];
    assign staged_departure_fuel_g = staged[191:160];
    assign staged_capture_fuel_g   = staged[223:192];

    // Last accepted command and its ACK, for exact retries.
    reg [15:0]  last_seq;
    reg [7:0]   last_type;
    reg [223:0] last_payload;
    reg [3:0]   last_detail;
    reg [31:0]  last_tick;
    reg [15:0]  last_crc;

    // ACK being sent.
    reg [7:0]  a_type;
    reg [15:0] a_seq;
    reg [3:0]  a_detail;
    reg [31:0] a_mission;
    reg [31:0] a_tick;
    reg [15:0] a_crc;

    assign ack_pending = (step != S_IDLE);
    assign ack_type    = 8'h80;
    assign ack_len     = 8'd16;
    assign ack_seq     = a_seq;
    assign ack_payload = {
        192'd0,
        16'h0000,                       // reserved
        a_crc,                          // plan_crc16
        a_tick,                         // applied_tick
        a_mission,                      // mission_id
        12'd0, a_detail,                // detail (u16)
        7'd0, (a_detail != D_OK),       // result: 0 applied, 1 rejected
        a_type                          // original_type
    };

    // ------------------------------------------------------------ plan CRC (LOAD_PLAN)
    reg [223:0] crc_shift;
    reg [4:0]   crc_left;
    reg [15:0]  crc;
    wire [15:0] crc_next;

    crc16 u_plan_crc (
        .crc_in  (crc),
        .data    (crc_shift[7:0]),
        .crc_out (crc_next)
    );

    // ------------------------------------------------------------ the checks
    // Fields of the command being handled.
    wire [31:0] c_mission   = f_payload[31:0];      // also the new session id for OPEN_SESSION
    wire [31:0] c_dep_tick  = f_payload[63:32];
    wire [31:0] c_arr_tick  = f_payload[95:64];
    wire [31:0] c_end_tick  = f_payload[127:96];
    wire [31:0] c_init_fuel = f_payload[159:128];
    wire [31:0] c_dep_fuel  = f_payload[191:160];
    wire [31:0] c_cap_fuel  = f_payload[223:192];
    wire [15:0] c_commit_crc = f_payload[47:32];
    wire [31:0] c_trip_days  = f_payload[63:32];     // SET_TRIP_DAYS

    assign set_days_value = c_trip_days;

    // Plan rules. The fuel sum is done in 33 bits so it cannot wrap.
    wire plan_bad = (c_mission == 32'd0)
                 || (c_dep_tick == 32'd0)
                 || !(c_dep_tick < c_arr_tick)
                 || !(c_arr_tick < c_end_tick)
                 || (c_end_tick > MAX_END_TICK)
                 || (c_dep_fuel == 32'd0)
                 || (c_cap_fuel == 32'd0)
                 || (({1'b0, c_dep_fuel} + {1'b0, c_cap_fuel}) > {1'b0, c_init_fuel});

    reg [3:0] detail;    // result of the checks
    reg       apply;     // command is accepted: do it
    reg       replay;    // exact retry: send the saved ACK
    reg       consume;   // this sequence number is now used

    always @(*) begin
        detail  = D_OK;
        apply   = 1'b0;
        replay  = 1'b0;
        consume = 1'b0;

        if (f_type == T_OPEN_SESSION) begin
            if (state != ST_IDLE)
                detail = D_BAD_STATE;
            else if (c_mission == 32'd0 || f_session != 32'd0)
                detail = D_BAD_SESSION;
            else
                apply = 1'b1;
        end else if (session == 32'd0 || f_session != session) begin
            detail = D_BAD_SESSION;
        end else if (f_seq == last_seq && last_seq != 16'd0) begin
            if (f_type == last_type && f_payload == last_payload)
                replay = 1'b1;
            else
                detail = D_SEQ_CONFLICT;
        end else if (f_seq < last_seq || f_seq == 16'd0) begin
            detail = D_STALE_SEQ;
        end else begin
            consume = 1'b1;
            case (f_type)
                T_LOAD_PLAN: begin
                    if (state != ST_IDLE)  detail = D_BAD_STATE;
                    else if (plan_bad)     detail = D_BAD_PLAN;
                    else                   apply  = 1'b1;
                end
                T_COMMIT_PLAN: begin
                    if (state != ST_IDLE)
                        detail = D_BAD_STATE;
                    else if (!staged_valid || staged_mission_id != c_mission)
                        detail = D_BAD_MISSION;
                    else if (staged_crc16 != c_commit_crc)
                        detail = D_BAD_PLAN_CRC;
                    else
                        apply = 1'b1;
                end
                default: begin      // ARM, START, ABORT, CLEAR need an active, matching mission
                    if (!plan_valid)
                        detail = D_BAD_STATE;
                    else if (plan_mission_id != c_mission)
                        detail = D_BAD_MISSION;
                    else if (f_type == T_ARM   && state != ST_LOADED)
                        detail = D_BAD_STATE;
                    else if (f_type == T_START && state != ST_ARMED)
                        detail = D_BAD_STATE;
                    else if (f_type == T_ABORT && !(state == ST_LOADED || state == ST_ARMED ||
                                                    state == ST_RUNNING || state == ST_SAFE))
                        detail = D_BAD_STATE;
                    else if (f_type == T_CLEAR && state == ST_RUNNING)
                        detail = D_BAD_STATE;
                    else if (f_type == T_SET_TRIP_DAYS && !(state == ST_LOADED || state == ST_ARMED))
                        detail = D_BAD_STATE;
                    else if (f_type == T_SET_TRIP_DAYS && (c_trip_days == 32'd0 || c_trip_days > 32'd9999))
                        detail = D_BAD_PLAN;
                    else
                        apply = 1'b1;
                end
            endcase
        end
    end

    // What the ACK reports, as things will be once the command is applied.
    reg [31:0] new_tick;
    reg [15:0] new_crc;

    always @(*) begin
        new_tick = tick_count;
        if      (plan_valid)   new_crc = plan_crc16;
        else if (staged_valid) new_crc = staged_crc16;
        else                   new_crc = 16'd0;

        if (apply) begin
            case (f_type)
                T_OPEN_SESSION: if (c_mission != session) new_crc = 16'd0;   // staged plan is dropped
                T_LOAD_PLAN:    new_crc = crc;                               // CRC of the plan just staged
                T_COMMIT_PLAN:  begin new_crc = staged_crc16; new_tick = 32'd0; end
                T_START:        new_tick = 32'd0;
                T_CLEAR:        begin new_crc = 16'd0; new_tick = 32'd0; end
                default: ;
            endcase
        end
    end

    // ------------------------------------------------------------ the steps
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            step         <= S_IDLE;
            f_type       <= 8'd0;
            f_seq        <= 16'd0;
            f_session    <= 32'd0;
            f_payload    <= 224'd0;
            staged_valid <= 1'b0;
            staged       <= 224'd0;
            staged_crc16 <= 16'd0;
            session      <= 32'd0;
            last_seq     <= 16'd0;
            last_type    <= 8'd0;
            last_payload <= 224'd0;
            last_detail  <= 4'd0;
            last_tick    <= 32'd0;
            last_crc     <= 16'd0;
            a_type       <= 8'd0;
            a_seq        <= 16'd0;
            a_detail     <= 4'd0;
            a_mission    <= 32'd0;
            a_tick       <= 32'd0;
            a_crc        <= 16'd0;
            crc_shift    <= 224'd0;
            crc_left     <= 5'd0;
            crc          <= 16'hFFFF;
            do_commit    <= 1'b0;
            do_arm       <= 1'b0;
            do_start     <= 1'b0;
            do_abort     <= 1'b0;
            do_clear     <= 1'b0;
            do_set_days  <= 1'b0;
            ack_start    <= 1'b0;
        end else begin
            do_commit <= 1'b0;
            do_arm    <= 1'b0;
            do_start  <= 1'b0;
            do_abort  <= 1'b0;
            do_clear  <= 1'b0;
            do_set_days <= 1'b0;
            ack_start <= 1'b0;

            case (step)
                // A command that arrives while another is still being
                // answered is ignored; the laptop sends one at a time.
                S_IDLE: begin
                    if (frame_valid && frame_type != 8'h01 && frame_type != 8'h03) begin
                        f_type    <= frame_type;
                        f_seq     <= frame_seq;
                        f_session <= frame_session;
                        f_payload <= frame_payload;
                        crc_shift <= frame_payload;
                        crc_left  <= 5'd28;
                        crc       <= 16'hFFFF;
                        step      <= (frame_type == T_LOAD_PLAN) ? S_CRC : S_DECIDE;
                    end
                end

                S_CRC: begin
                    crc       <= crc_next;
                    crc_shift <= {8'h00, crc_shift[223:8]};
                    crc_left  <= crc_left - 5'd1;
                    if (crc_left == 5'd1)
                        step <= S_DECIDE;
                end

                S_DECIDE: begin
                    a_type    <= f_type;
                    a_seq     <= f_seq;
                    a_mission <= (f_type == T_OPEN_SESSION) ? 32'd0 : c_mission;

                    if (replay) begin
                        a_detail <= last_detail;
                        a_tick   <= last_tick;
                        a_crc    <= last_crc;
                    end else begin
                        a_detail <= detail;
                        a_tick   <= new_tick;
                        a_crc    <= new_crc;
                    end

                    if (consume) begin
                        last_seq     <= f_seq;
                        last_type    <= f_type;
                        last_payload <= f_payload;
                        last_detail  <= detail;
                        last_tick    <= new_tick;
                        last_crc     <= new_crc;
                    end

                    if (apply) begin
                        case (f_type)
                            T_OPEN_SESSION: begin
                                // A repeat with the same id keeps the history.
                                if (c_mission != session) begin
                                    session      <= c_mission;
                                    last_seq     <= 16'd0;
                                    staged_valid <= 1'b0;
                                end
                            end
                            T_LOAD_PLAN: begin
                                staged       <= f_payload;
                                staged_crc16 <= crc;
                                staged_valid <= 1'b1;
                            end
                            T_COMMIT_PLAN: begin
                                do_commit    <= 1'b1;
                                staged_valid <= 1'b0;
                            end
                            T_ARM:   do_arm   <= 1'b1;
                            T_START: do_start <= 1'b1;
                            T_ABORT: do_abort <= 1'b1;
                            T_CLEAR: begin
                                do_clear     <= 1'b1;
                                staged_valid <= 1'b0;
                            end
                            T_SET_TRIP_DAYS: do_set_days <= 1'b1;
                            default: ;
                        endcase
                    end

                    step <= S_ACK;
                end

                S_ACK: begin
                    if (tx_free && !ack_start) begin
                        ack_start <= 1'b1;
                        step      <= S_IDLE;
                    end
                end
            endcase
        end
    end

endmodule
