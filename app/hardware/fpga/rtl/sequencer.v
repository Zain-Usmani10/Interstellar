// sequencer.v
// The mission itself: the active plan, the mission state, the tick counter,
// the fuel ledger and the two burn events, with fault tolerance.
//
// The plan is seven numbers from the laptop:
//   mission_id, departure_tick, arrival_tick, end_tick,
//   initial_fuel_g, departure_fuel_g, capture_fuel_g
//
// States (same numbers as on the wire):
//   0 IDLE  1 LOADED  2 ARMED  3 RUNNING  4 SAFE  5 COMPLETE  6 ABORTED
//
// While RUNNING:
//   - tick_count goes up by 1 on every 100 Hz tick.
//   - Once tick_count >= departure_tick: subtract departure_fuel_g, set
//     mask bit 0, remember the tick. Fires once.
//   - Once tick_count >= arrival_tick (and departure is done): subtract
//     capture_fuel_g, set mask bit 1, remember the tick, COMPLETE.
//   - If a burn costs more fuel than is left: no burn, state SAFE.
// The clock keeps counting in SAFE and ABORTED until end_tick (the
// spacecraft keeps coasting). COMPLETE and CLEAR stop it.
//
// Fault tolerance (spec section 9):
//   The "control tuple" = state, executed mask, fuel, and the two burn
//   ticks. It is stored three times (tmr_lanes) and voted (voter).
//     - Two or three copies agree: use that value. If one copy differed,
//       masked_fault_count goes up and the copy is repaired next clock.
//     - All three differ: no majority. no_majority_count goes up, the last
//       good value is used, and an ARMED or RUNNING mission is forced to
//       SAFE, which blocks all future burns.
//   NOT triplicated, on purpose: the plan, the tick counter, the voter and
//   this supervisor logic. They are single points of failure.
//
// Fault switches (demo): inject_single flips one bit in lane A.
// inject_divergence flips different bits in lanes A and B on the same
// clock. Neither touches the safety logic directly; SAFE only happens
// because the voter really sees three different copies.
//
// The do_* inputs are one-clock pulses from cmd_handler, which has already
// checked that each command is allowed. local_abort is the board's own
// abort button.

module sequencer (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        tick,               // mission 100 Hz enable

    // checked commands from cmd_handler
    input  wire        do_commit,          // activate the staged plan
    input  wire        do_arm,
    input  wire        do_start,
    input  wire        do_abort,
    input  wire        do_clear,

    // board controls (one-clock pulses)
    input  wire        local_abort,
    input  wire        inject_single,
    input  wire        inject_divergence,

    // staged plan, copied on do_commit
    input  wire [31:0] staged_mission_id,
    input  wire [31:0] staged_departure_tick,
    input  wire [31:0] staged_arrival_tick,
    input  wire [31:0] staged_end_tick,
    input  wire [31:0] staged_initial_fuel_g,
    input  wire [31:0] staged_departure_fuel_g,
    input  wire [31:0] staged_capture_fuel_g,
    input  wire [15:0] staged_crc16,

    // mission status (state, mask, fuel and burn ticks are the voted values)
    output reg         plan_valid,         // a plan is active
    output reg  [31:0] mission_id,         // 0 when no plan
    output reg  [15:0] plan_crc16,         // 0 when no plan
    output wire [2:0]  state,
    output reg  [31:0] tick_count,
    output wire [1:0]  executed_mask,      // bit 0 departure, bit 1 capture
    output wire [31:0] fuel_g,
    output wire [31:0] departure_executed_tick,   // FFFFFFFF = not yet
    output wire [31:0] capture_executed_tick,     // FFFFFFFF = not yet
    output reg  [2:0]  safe_reason,        // 0 none, 1 no majority, 2 illegal state, 3 fuel
    output reg  [31:0] masked_fault_count,
    output reg  [31:0] no_majority_count,

    output reg         tick_restart,       // restarts the mission tick divider
    output reg         changed             // pulse: something worth a STATUS happened
);

    localparam [2:0] ST_IDLE     = 3'd0,
                     ST_LOADED   = 3'd1,
                     ST_ARMED    = 3'd2,
                     ST_RUNNING  = 3'd3,
                     ST_SAFE     = 3'd4,
                     ST_COMPLETE = 3'd5,
                     ST_ABORTED  = 3'd6;

    localparam [2:0]  SAFE_NONE        = 3'd0,
                      SAFE_NO_MAJORITY = 3'd1,
                      SAFE_ILLEGAL     = 3'd2,
                      SAFE_FUEL        = 3'd3;
    localparam [31:0] UNSET            = 32'hFFFF_FFFF;

    // ------------------------------------------------------------ control tuple
    // {state(3), mask(2), fuel(32), departure tick(32), capture tick(32)}
    localparam integer W = 101;
    localparam [W-1:0] TUPLE_RESET = {ST_IDLE, 2'b00, 32'd0, UNSET, UNSET};

    // Demo faults: which stored bit each switch flips (fuel bits 4 and 7).
    localparam [W-1:0] FLIP_A = {{(W-69){1'b0}}, 1'b1, 68'd0};   // tuple bit 68
    localparam [W-1:0] FLIP_B = {{(W-72){1'b0}}, 1'b1, 71'd0};   // tuple bit 71

    wire [W-1:0] lane_a, lane_b, lane_c;
    wire [W-1:0] voted;
    wire         majority_ok;
    wire         mismatch;
    reg  [W-1:0] next_tuple;

    wire inject_any = inject_single | inject_divergence;

    tmr_lanes #(
        .W           (W),
        .RESET_VALUE (TUPLE_RESET)
    ) u_lanes (
        .clk    (clk),
        .rst_n  (rst_n),
        .next   (next_tuple),
        .flip_a (inject_any        ? FLIP_A : {W{1'b0}}),
        .flip_b (inject_divergence ? FLIP_B : {W{1'b0}}),
        .lane_a (lane_a),
        .lane_b (lane_b),
        .lane_c (lane_c)
    );

    voter #(.W(W)) u_voter (
        .a           (lane_a),
        .b           (lane_b),
        .c           (lane_c),
        .voted       (voted),
        .majority_ok (majority_ok),
        .mismatch    (mismatch)
    );

    // ------------------------------------------------------------ supervisor
    // The last value written to the lanes. Used only when there is no
    // majority.
    (* preserve, dont_merge *) reg [W-1:0] last_good;

    wire [W-1:0] trusted = majority_ok ? voted : last_good;

    wire [2:0]  t_state = trusted[100:98];
    wire [1:0]  t_mask  = trusted[97:96];
    wire [31:0] t_fuel  = trusted[95:64];
    wire [31:0] t_dep   = trusted[63:32];
    wire [31:0] t_cap   = trusted[31:0];

    wire no_majority   = !majority_ok;
    wire masked_fault  = majority_ok && mismatch;
    wire illegal_state = (t_state == 3'd7);

    // No majority is unsafe only while a mission could still fire a burn.
    wire force_safe_nm = no_majority && (t_state == ST_ARMED || t_state == ST_RUNNING);

    // The values the rest of the board works with.
    assign state         = (force_safe_nm || illegal_state) ? ST_SAFE : t_state;
    assign executed_mask = t_mask;
    assign fuel_g        = t_fuel;
    assign departure_executed_tick = t_dep;
    assign capture_executed_tick   = t_cap;

    // ------------------------------------------------------------ active plan and mission clock
    reg [31:0] departure_tick;
    reg [31:0] arrival_tick;
    reg [31:0] end_tick;
    reg [31:0] departure_fuel_g;
    reg [31:0] capture_fuel_g;
    reg        clock_running;      // mission clock latch (set by START)

    wire [31:0] next_tick = tick_count + 32'd1;
    wire        step      = tick && clock_running;

    wire abort_now = (do_abort || local_abort) &&
                     (state == ST_LOADED || state == ST_ARMED ||
                      state == ST_RUNNING || state == ST_SAFE);

    // A burn is due. Not on the clock a fault is injected: the corrupted
    // copies must be voted first (one 50 MHz cycle later). Commands that
    // stop the mission win.
    wire burn_allowed  = (state == ST_RUNNING) && !inject_any && !abort_now && !do_clear;
    wire departure_due = burn_allowed && !t_mask[0] && (tick_count >= departure_tick);
    wire capture_due   = burn_allowed && (t_mask == 2'b01) && (tick_count >= arrival_tick);

    wire departure_ok  = departure_due && !(departure_fuel_g > t_fuel);
    wire capture_ok    = capture_due   && !(capture_fuel_g   > t_fuel);
    wire fuel_fault    = (departure_due && !departure_ok) || (capture_due && !capture_ok);

    // ------------------------------------------------------------ next control tuple
    reg [2:0]  n_state;
    reg [1:0]  n_mask;
    reg [31:0] n_fuel;
    reg [31:0] n_dep;
    reg [31:0] n_cap;

    always @(*) begin
        n_state = state;
        n_mask  = t_mask;
        n_fuel  = t_fuel;
        n_dep   = t_dep;
        n_cap   = t_cap;

        // Scheduled burns (lowest priority).
        if (departure_ok) begin
            n_fuel    = t_fuel - departure_fuel_g;
            n_mask[0] = 1'b1;
            n_dep     = tick_count;
        end else if (capture_ok) begin
            n_fuel    = t_fuel - capture_fuel_g;
            n_mask[1] = 1'b1;
            n_cap     = tick_count;
            n_state   = ST_COMPLETE;
        end else if (fuel_fault) begin
            n_state   = ST_SAFE;
        end

        // Commands.
        if (do_commit) begin
            n_state = ST_LOADED;
            n_mask  = 2'b00;
            n_fuel  = staged_initial_fuel_g;
            n_dep   = UNSET;
            n_cap   = UNSET;
        end
        if (do_arm)    n_state = ST_ARMED;
        if (do_start)  n_state = ST_RUNNING;
        if (abort_now) n_state = ST_ABORTED;
        if (do_clear) begin
            n_state = ST_IDLE;
            n_mask  = 2'b00;
            n_fuel  = 32'd0;
            n_dep   = UNSET;
            n_cap   = UNSET;
        end

        next_tuple = {n_state, n_mask, n_fuel, n_dep, n_cap};
    end

    // ------------------------------------------------------------ everything that is not triplicated
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            last_good          <= TUPLE_RESET;
            plan_valid         <= 1'b0;
            mission_id         <= 32'd0;
            plan_crc16         <= 16'd0;
            departure_tick     <= 32'd0;
            arrival_tick       <= 32'd0;
            end_tick           <= 32'd0;
            departure_fuel_g   <= 32'd0;
            capture_fuel_g     <= 32'd0;
            tick_count         <= 32'd0;
            clock_running      <= 1'b0;
            safe_reason        <= SAFE_NONE;
            masked_fault_count <= 32'd0;
            no_majority_count  <= 32'd0;
            tick_restart       <= 1'b0;
            changed            <= 1'b0;
        end else begin
            last_good    <= next_tuple;
            tick_restart <= 1'b0;

            // Tell status_gen when something visible changed.
            changed <= (n_state != t_state) || (n_mask != t_mask)
                    || do_commit || do_start || do_clear
                    || masked_fault || no_majority;

            // Fault counters. They survive CLEAR; only reset clears them.
            if (masked_fault) masked_fault_count <= masked_fault_count + 32'd1;
            if (no_majority)  no_majority_count  <= no_majority_count  + 32'd1;

            // Why the board is in SAFE.
            if (force_safe_nm)      safe_reason <= SAFE_NO_MAJORITY;
            else if (illegal_state) safe_reason <= SAFE_ILLEGAL;
            else if (fuel_fault)    safe_reason <= SAFE_FUEL;

            // Mission time. Stops at end_tick, and at the capture burn.
            if (step) begin
                tick_count <= next_tick;
                if (next_tick >= end_tick)
                    clock_running <= 1'b0;
            end
            if (capture_ok)
                clock_running <= 1'b0;

            // Commands. Written last, so they win over the above.
            if (do_commit) begin
                plan_valid       <= 1'b1;
                mission_id       <= staged_mission_id;
                plan_crc16       <= staged_crc16;
                departure_tick   <= staged_departure_tick;
                arrival_tick     <= staged_arrival_tick;
                end_tick         <= staged_end_tick;
                departure_fuel_g <= staged_departure_fuel_g;
                capture_fuel_g   <= staged_capture_fuel_g;
                tick_count       <= 32'd0;
                safe_reason      <= SAFE_NONE;
            end

            if (do_start) begin
                tick_count    <= 32'd0;
                clock_running <= 1'b1;
                tick_restart  <= 1'b1;       // first tick is one full period away
            end

            if (do_clear) begin
                plan_valid    <= 1'b0;
                mission_id    <= 32'd0;
                plan_crc16    <= 16'd0;
                tick_count    <= 32'd0;
                clock_running <= 1'b0;
                safe_reason   <= SAFE_NONE;
            end
        end
    end

endmodule
