// tb_cockpit.v
// SIMULATION ONLY. Passing here does not mean the board works.
//
// The shuttle / control-station extension (docs/SHUTTLE_CCS_EXTENSION.md in
// the FPGA folder): SET_TRIP_DAYS, days to arrival, the link watchdog and
// the seven-segment cockpit readout. All plans here are dummy data: short
// trips that are flown tick by tick with no shortcut.
//
//   K1  SET_TRIP_DAYS accept / reject rules. A 300-day trip in 60 ticks:
//       days to arrival checked against the shared formula on every tick,
//       the T-minus readout, link lost after 30 silent ticks (2 s on the
//       real board), "nL" blinking, link back on the next frame, and the
//       mission completing anyway. CLEAR forgets the trip length.
//   K2  A 7-day trip in 60 ticks.
//   K3  A 1000-day trip in 30 ticks. A new plan forgets the old length.
//   K4  No SET_TRIP_DAYS (a backend that does not know the command): the
//       mission runs as before and the display shows seconds elapsed.
//   K5  Contracts 1.2.0 golden frames: 31 -> ACK 32 byte for byte, the
//       identical retry, and a 0-day request -> NACK 33 byte for byte.
//   K6  Plan section 19 timing (500 / 6500 / 6800): first countdown ticks only.
//
// The monitor, senders and check tasks below are the same as in tb_mission.v.

`timescale 1ns / 1ps

module tb_cockpit;

    reg clk = 1'b0;
    always #10 clk = ~clk;           // 50 MHz

    integer errors = 0;

    task check;
        input         ok;
        input [639:0] what;
        begin
            if (!ok) begin
                errors = errors + 1;
                $display("FAIL  %0s  (t=%0t)", what, $time);
            end else begin
                $display("ok    %0s", what);
            end
        end
    endtask

    localparam integer BIT  = 8;         // clocks per UART bit
    localparam integer TICK = 10_000;    // clocks per 100 Hz tick (real: 500,000)

    // Golden values (see fixtures/frames/manifest.json).
    localparam [31:0] SESSION   = 32'h1A2B3C4D;
    localparam [31:0] MISSION   = 32'h00C0FFEE;
    localparam [15:0] PLAN_CRC  = 16'd61175;
    localparam [31:0] DEP_TICK  = 32'd10;
    localparam [31:0] ARR_TICK  = 32'd12010;
    localparam [31:0] END_TICK  = 32'd12610;
    localparam [31:0] INIT_FUEL = 32'd1760979;
    localparam [31:0] DEP_FUEL  = 32'd1179314;
    localparam [31:0] CAP_FUEL  = 32'd581665;

    // ---------------------------------------------------------- DUT
    reg  [1:0] key  = 2'b11;
    reg        line = 1'b1;
    wire       tx_line;
    wire [9:0] ledr;
    wire [7:0] hex0, hex1, hex2, hex3, hex4, hex5;

    interstellar_top #(
        .TICK_DIVISOR         (TICK),
        .HEARTBEAT_HALF_TICKS (5),
        .UART_CLKS_PER_BIT    (BIT),
        .FRAME_TIMEOUT_CLKS   (200_000),
        .LINK_TIMEOUT_TICKS   (30)
    ) dut (
        .MAX10_CLK1_50 (clk),
        .KEY           (key),
        .SW            (2'b00),
        .UART_RX       (line),
        .UART_TX       (tx_line),
        .LEDR          (ledr),
        .HEX0 (hex0), .HEX1 (hex1), .HEX2 (hex2),
        .HEX3 (hex3), .HEX4 (hex4), .HEX5 (hex5)
    );

    // ---------------------------------------------------------- monitor: split the board's output into frames
    reg        mon_rst_n = 1'b0;
    wire [7:0] mon_data;
    wire       mon_valid;
    wire       mon_ferr;

    uart_rx #(.CLKS_PER_BIT(BIT)) u_monitor (
        .clk(clk), .rst_n(mon_rst_n), .rx(tx_line),
        .data(mon_data), .valid(mon_valid), .frame_error(mon_ferr)
    );

    function [15:0] crc_step;
        input [15:0] crc;
        input [7:0]  d;
        integer b;
        reg [15:0] c;
        begin
            c = crc ^ {d, 8'h00};
            for (b = 0; b < 8; b = b + 1)
                c = c[15] ? ({c[14:0], 1'b0} ^ 16'h1021) : {c[14:0], 1'b0};
            crc_step = c;
        end
    endfunction

    reg [7:0] cur [0:255];           // frame being received
    integer   cur_n = 0;
    reg [7:0] ack [0:63];            // last ACK frame
    integer   ack_n = 0;
    integer   ack_count = 0;
    reg [7:0] st [0:63];             // last STATUS frame
    integer   st_count = 0;
    integer   bad_frames = 0;        // malformed output from the board
    integer   j;
    reg [15:0] mcrc;

    always @(posedge clk) begin
        if (mon_ferr) bad_frames = bad_frames + 1;
        if (mon_valid) begin
            cur[cur_n] = mon_data;
            cur_n = cur_n + 1;
            if (cur_n >= 12 && cur_n == 14 + cur[10]) begin
                mcrc = 16'hFFFF;
                for (j = 2; j < cur_n - 2; j = j + 1) mcrc = crc_step(mcrc, cur[j]);
                if (cur[0] !== 8'hA5 || cur[1] !== 8'h5A || cur[2] !== 8'h01 ||
                    cur[cur_n-2] !== mcrc[7:0] || cur[cur_n-1] !== mcrc[15:8]) begin
                    bad_frames = bad_frames + 1;
                end else if (cur[3] == 8'h80 && cur_n == 30) begin
                    for (j = 0; j < cur_n; j = j + 1) ack[j] = cur[j];
                    ack_n = cur_n;
                    ack_count = ack_count + 1;
                end else if (cur[3] == 8'h81 && cur_n == 54) begin
                    for (j = 0; j < cur_n; j = j + 1) st[j] = cur[j];
                    st_count = st_count + 1;
                end else begin
                    bad_frames = bad_frames + 1;
                end
                cur_n = 0;
            end
        end
    end

    // ---------------------------------------------------------- fixture files
    reg [7:0] file_mem [0:255];
    integer   file_n;
    reg [7:0] exp_mem [0:255];
    integer   exp_n;
    integer   i;

    task load_file;
        input [1023:0] path;
        begin
            for (i = 0; i < 256; i = i + 1) file_mem[i] = 8'hxx;
            $readmemh(path, file_mem);
            file_n = 0;
            while (file_n < 256 && file_mem[file_n] !== 8'hxx) file_n = file_n + 1;
            if (file_n == 0) begin
                errors = errors + 1;
                $display("FAIL  could not read fixture %0s", path);
            end
        end
    endtask

    task load_expected;
        input [1023:0] path;
        begin
            for (i = 0; i < 256; i = i + 1) exp_mem[i] = 8'hxx;
            $readmemh(path, exp_mem);
            exp_n = 0;
            while (exp_n < 256 && exp_mem[exp_n] !== 8'hxx) exp_n = exp_n + 1;
            if (exp_n == 0) begin
                errors = errors + 1;
                $display("FAIL  could not read fixture %0s", path);
            end
        end
    endtask

    // ---------------------------------------------------------- sending
    task send_byte;
        input [7:0] b;
        integer k;
        begin
            @(negedge clk);
            line = 1'b0;
            repeat (BIT) @(negedge clk);
            for (k = 0; k < 8; k = k + 1) begin
                line = b[k];
                repeat (BIT) @(negedge clk);
            end
            line = 1'b1;
            repeat (BIT) @(negedge clk);
        end
    endtask

    task send_loaded_file;
        integer n;
        begin
            for (n = 0; n < file_n; n = n + 1) send_byte(file_mem[n]);
        end
    endtask

    // Build a host frame and send it. Payload byte 0 is bits [7:0].
    reg [7:0]  fb [0:63];
    reg [15:0] fcrc;
    task send_frame;
        input [7:0]   t;
        input [15:0]  seq;
        input [31:0]  sess;
        input [223:0] pay;
        input integer len;
        integer n;
        begin
            fb[0] = 8'hA5;        fb[1] = 8'h5A;         fb[2] = 8'h01;        fb[3] = t;
            fb[4] = seq[7:0];     fb[5] = seq[15:8];
            fb[6] = sess[7:0];    fb[7] = sess[15:8];    fb[8] = sess[23:16];  fb[9] = sess[31:24];
            fb[10] = len;         fb[11] = 8'h00;
            for (n = 0; n < len; n = n + 1) fb[12 + n] = pay[n * 8 +: 8];
            fcrc = 16'hFFFF;
            for (n = 2; n < 12 + len; n = n + 1) fcrc = crc_step(fcrc, fb[n]);
            fb[12 + len] = fcrc[7:0];
            fb[13 + len] = fcrc[15:8];
            for (n = 0; n < 14 + len; n = n + 1) send_byte(fb[n]);
        end
    endtask

    // ---------------------------------------------------------- waiting
    integer guard;
    integer n0;

    task wait_tx_idle;
        begin
            guard = 0;
            while ((dut.ftx_busy || dut.st_pending || dut.ack_pending || dut.tx_busy) && guard < 60_000) begin
                @(posedge clk);
                guard = guard + 1;
            end
            repeat (BIT * 2) @(posedge clk);
        end
    endtask

    task wait_ack;                   // until ack_count passes n0
        begin
            guard = 0;
            while (ack_count == n0 && guard < 60_000) begin
                @(posedge clk);
                guard = guard + 1;
            end
        end
    endtask

    task wait_status;                // until st_count passes n0
        begin
            guard = 0;
            while (st_count == n0 && guard < 60_000) begin
                @(posedge clk);
                guard = guard + 1;
            end
        end
    endtask

    task wait_tick;                  // until the mission tick counter reaches v
        input [31:0] v;
        begin
            guard = 0;
            while (dut.tick_count != v && guard < 40 * TICK) begin
                @(posedge clk);
                guard = guard + 1;
            end
        end
    endtask

    // Test shortcut (see the header): jump mission time to tick v, with a
    // full tick period before the next tick.
    task set_tick;
        input [31:0] v;
        begin
            wait_tx_idle;
            @(negedge clk);
            dut.u_sequencer.tick_count = v;
            dut.u_mission_tick.count   = 32'd0;
        end
    endtask

    // ---------------------------------------------------------- checks
    integer match;

    task check_ack_equals;           // last ACK frame == fixture, byte for byte
        input [1023:0] path;
        input [639:0]  what;
        begin
            load_expected(path);
            match = (ack_count != n0) && (ack_n == exp_n);
            for (i = 0; i < exp_n; i = i + 1)
                if (ack[i] !== exp_mem[i]) match = 0;
            check(match, what);
            if (!match) begin
                $write("      got:");
                for (i = 0; i < ack_n; i = i + 1) $write(" %02X", ack[i]);
                $write("\n");
            end
        end
    endtask

    // Send a fixture request, expect a fixture ACK.
    task cmd_file;
        input [1023:0] req_path;
        input [1023:0] ack_path;
        input [639:0]  what;
        begin
            load_file(req_path);
            n0 = ack_count;
            send_loaded_file;
            wait_ack;
            check_ack_equals(ack_path, what);
        end
    endtask

    // Send a built request, expect a fixture ACK.
    task cmd_built;
        input [7:0]    t;
        input [15:0]   seq;
        input [31:0]   sess;
        input [223:0]  pay;
        input integer  len;
        input [1023:0] ack_path;
        input [639:0]  what;
        begin
            n0 = ack_count;
            send_frame(t, seq, sess, pay, len);
            wait_ack;
            check_ack_equals(ack_path, what);
        end
    endtask

    // Send a built request, expect an ACK with this detail code.
    task cmd_detail;
        input [7:0]    t;
        input [15:0]   seq;
        input [31:0]   sess;
        input [223:0]  pay;
        input integer  len;
        input [7:0]    detail;
        input [639:0]  what;
        begin
            n0 = ack_count;
            send_frame(t, seq, sess, pay, len);
            wait_ack;
            check(ack_count != n0 && ack[12] == t && ack[14] == detail && ack[15] == 8'h00 &&
                  ack[13] == ((detail == 8'd0) ? 8'h00 : 8'h01), what);
        end
    endtask

    // Ask for STATUS; its session and 40-byte payload must equal the fixture.
    task check_status_equals;
        input [1023:0] path;
        input [639:0]  what;
        begin
            load_expected(path);
            wait_tx_idle;
            n0 = st_count;
            send_frame(8'h03, 16'd0, 32'd0, 224'd0, 0);       // GET_STATUS
            wait_status;
            match = (st_count != n0);
            for (i = 6; i < 10; i = i + 1)
                if (st[i] !== exp_mem[i]) match = 0;
            for (i = 12; i < 52; i = i + 1)
                if (st[i] !== exp_mem[i]) match = 0;
            check(match, what);
            if (!match) begin
                $write("      got:");
                for (i = 0; i < 54; i = i + 1) $write(" %02X", st[i]);
                $write("\n");
            end
        end
    endtask

    task reset_board;
        begin
            wait_tx_idle;
            @(negedge clk);
            key[0]    = 1'b0;
            mon_rst_n = 1'b0;
            repeat (20) @(posedge clk);
            cur_n = 0;
            @(negedge clk);
            key[0]    = 1'b1;
            mon_rst_n = 1'b1;
            repeat (20) @(posedge clk);
        end
    endtask

    wire [223:0] MISSION_PAY = {192'd0, MISSION};

    // ---------------------------------------------------------- reading the displays
    // Segment patterns, active low, {g,f,e,d,c,b,a} (same table as seg7.v).
    localparam [6:0] P_DASH = ~7'b1000000, P_1 = ~7'b0000110, P_5 = ~7'b1101101,
                     P_d = ~7'b1011110, P_L = ~7'b0111000, P_A = ~7'b1110111,
                     P_r = ~7'b1010000, P_n = ~7'b1010100, P_F = ~7'b1110001,
                     P_C = ~7'b0111001, P_o = ~7'b1011100, P_b = ~7'b1111100;

    function integer seg_digit;      // 0..9, or 1000000 if it is not a digit
        input [6:0] seg;
        begin
            case (~seg)
                7'b0111111: seg_digit = 0;
                7'b0000110: seg_digit = 1;
                7'b1011011: seg_digit = 2;
                7'b1001111: seg_digit = 3;
                7'b1100110: seg_digit = 4;
                7'b1101101: seg_digit = 5;
                7'b1111101: seg_digit = 6;
                7'b0000111: seg_digit = 7;
                7'b1111111: seg_digit = 8;
                7'b1101111: seg_digit = 9;
                default:    seg_digit = 1000000;
            endcase
        end
    endfunction

    // The number on HEX3..HEX0.
    wire [31:0] shown = seg_digit(hex3[6:0]) * 1000 + seg_digit(hex2[6:0]) * 100
                      + seg_digit(hex1[6:0]) * 10   + seg_digit(hex0[6:0]);
    wire dashes  = (hex3[6:0] == P_DASH) && (hex2[6:0] == P_DASH) &&
                   (hex1[6:0] == P_DASH) && (hex0[6:0] == P_DASH);
    wire point   = !hex2[7];                         // the SS.cc decimal point is lit
    wire no_other_points = hex0[7] && hex1[7] && hex3[7] && hex4[7] && hex5[7];

    task settle;                     // let the decimal converter catch up
        begin
            repeat (120) @(posedge clk);
        end
    endtask

    task check_letters;
        input [6:0]   a;
        input [6:0]   b;
        input [639:0] what;
        begin
            check(hex5[6:0] === a && hex4[6:0] === b, what);
        end
    endtask

    // ---------------------------------------------------------- commands
    integer seq;

    task cmd;                        // next sequence number, expect this detail code
        input [7:0]   t;
        input [223:0] pay;
        input integer len;
        input [7:0]   detail;
        input [639:0] what;
        begin
            seq = seq + 1;
            cmd_detail(t, seq, SESSION, pay, len, detail, what);
        end
    endtask

    task load_commit;                // a dummy plan with the golden fuel numbers
        input [31:0] dep;
        input [31:0] arr;
        input [31:0] endt;
        begin
            cmd(8'h10, {CAP_FUEL, DEP_FUEL, INIT_FUEL, endt, arr, dep, MISSION}, 28, 8'd0, "LOAD_PLAN applied");
            cmd(8'h11, {176'd0, dut.staged_crc16, MISSION}, 6, 8'd0, "COMMIT_PLAN applied");
        end
    endtask

    task set_days;
        input [31:0]  mission;
        input [31:0]  days;
        input [7:0]   detail;
        input [639:0] what;
        begin
            cmd(8'h16, {160'd0, days, mission}, 8, detail, what);
        end
    endtask

    // ---------------------------------------------------------- flying a plan in real ticks
    // Called right after START. Walks every tick up to the arrival tick and
    // compares the board with the shared formula
    //   elapsed_days = floor((tick - dep) * days / (arr - dep))
    // and with what the displays should show.
    //
    // link_test: stay silent from START on, expect "link lost" and the "nL"
    // blink, send one GET_STATUS at tick 50, expect the link back.
    integer bad_days, bad_disp, bad_link;
    integer seen_nl, seen_rn;
    integer t;
    reg [31:0] exp_left;
    reg [31:0] exp_shown;

    task fly;
        input [31:0] dep;
        input [31:0] arr;
        input [31:0] days;
        input        has_days;
        input        link_test;
        begin
            bad_days = 0; bad_disp = 0; bad_link = 0; seen_nl = 0; seen_rn = 0;
            for (t = 1; t <= arr; t = t + 1) begin
                wait_tick(t);
                repeat (400) @(posedge clk);

                if (t <= dep) exp_left = days;
                else          exp_left = days - ((t - dep) * days) / (arr - dep);

                if (has_days && dut.days_to_arrival !== exp_left) begin
                    bad_days = bad_days + 1;
                    $display("      tick %0d: days_to_arrival %0d, expected %0d", t, dut.days_to_arrival, exp_left);
                end

                if (t < dep) begin                               // T-minus SS.cc
                    if (shown !== dep - t || !point) bad_disp = bad_disp + 1;
                end else begin
                    exp_shown = has_days ? (exp_left % 10000) : (t / 100);
                    if (shown !== exp_shown || point) begin
                        bad_disp = bad_disp + 1;
                        $display("      tick %0d: display %0d, expected %0d", t, shown, exp_shown);
                    end
                end
                if (!no_other_points) bad_disp = bad_disp + 1;

                if (link_test) begin
                    if (t == 25 && dut.link_lost !== 1'b0) bad_link = bad_link + 1;
                    if (t >= 35 && t < 50) begin
                        if (dut.link_lost !== 1'b1) bad_link = bad_link + 1;
                        if (dut.heartbeat_led) begin
                            if (hex5[6:0] === P_n && hex4[6:0] === P_L) seen_nl = seen_nl + 1;
                            else bad_link = bad_link + 1;
                        end else begin
                            if (hex5[6:0] === P_r && hex4[6:0] === P_n) seen_rn = seen_rn + 1;
                            else bad_link = bad_link + 1;
                        end
                    end
                    if (t == 50) begin
                        send_frame(8'h03, 16'd0, 32'd0, 224'd0, 0);       // GET_STATUS
                        repeat (200) @(posedge clk);
                        if (dut.link_lost !== 1'b0) bad_link = bad_link + 1;
                    end
                    if (t == 55 && (dut.link_lost !== 1'b0 || hex5[6:0] !== P_r || hex4[6:0] !== P_n))
                        bad_link = bad_link + 1;
                end
            end
            settle;
        end
    endtask

    initial begin
        // =========================================================== K1
        $display("--- K1: SET_TRIP_DAYS rules, 300-day trip in 60 ticks, link lost and back");
        reset_board;
        seq = 0;
        repeat (40 * TICK) @(posedge clk);
        check(dut.link_seen === 1'b0 && dut.link_lost === 1'b0,
              "no link was ever seen: not reported as lost");
        check_letters(P_1, P_d, "display shows Id");
        check(dashes, "number shows ----");

        cmd_detail(8'h02, 16'd0, 32'd0, {192'd0, SESSION}, 4, 8'd0, "OPEN_SESSION applied");
        check(dut.link_seen === 1'b1, "link seen after the first frame");
        set_days(MISSION, 32'd300, 8'd1, "SET_TRIP_DAYS with no plan -> BAD_STATE");

        load_commit(32'd20, 32'd80, 32'd100);
        settle;
        check_letters(P_L, P_d, "display shows Ld");
        check(dashes, "number shows ---- until the trip length is set");

        set_days(32'h0BADBEEF, 32'd300,   8'd2, "wrong mission -> BAD_MISSION");
        set_days(MISSION,      32'd0,     8'd4, "0 days -> BAD_PLAN");
        set_days(MISSION,      32'd10000, 8'd4, "10000 days -> BAD_PLAN");
        check(dut.trip_days_valid === 1'b0, "rejected commands did not set a trip length");
        set_days(MISSION,      32'd300,   8'd0, "300 days applied (LOADED)");
        settle;
        check(dut.trip_days_valid === 1'b1 && dut.trip_days == 32'd300, "trip length is 300");
        check(shown == 32'd300 && !point, "number shows 0300");

        cmd(8'h12, MISSION_PAY, 4, 8'd0, "ARM applied");
        set_days(MISSION, 32'd9999, 8'd0, "9999 days applied (ARMED)");
        settle;
        check_letters(P_A, P_r, "display shows Ar");
        check(shown == 32'd9999, "number shows 9999");
        set_days(MISSION, 32'd300, 8'd0, "back to 300 days");

        cmd(8'h13, MISSION_PAY, 4, 8'd0, "START applied");
        set_days(MISSION, 32'd777, 8'd1, "SET_TRIP_DAYS while RUNNING -> BAD_STATE");
        check(dut.trip_days == 32'd300, "trip length unchanged by the rejected command");

        fly(32'd20, 32'd80, 32'd300, 1'b1, 1'b1);
        check(bad_days == 0, "days to arrival equals the formula on every tick 1..80");
        check(bad_disp == 0, "display: T-minus SS.cc before the burn, days after, every tick");
        check(bad_link == 0, "link lost after 30 silent ticks, back on the next frame");
        check(seen_nl > 0 && seen_rn > 0, "display alternated nL / rn while the link was lost");
        check(dut.state == 3'd5 && dut.executed_mask == 2'b11 &&
              dut.fuel_g == INIT_FUEL - DEP_FUEL - CAP_FUEL,
              "mission COMPLETE with both burns although the link dropped mid-flight");
        check(dut.days_to_arrival == 32'd0 && shown == 32'd0, "0 days to arrival at the capture burn");
        // The link timed out again during the silent last 30 ticks; the next
        // command brings it back, so the state letters are steady again.
        set_days(MISSION, 32'd300, 8'd1, "SET_TRIP_DAYS after COMPLETE -> BAD_STATE");
        check_letters(P_C, P_o, "display shows Co");
        cmd(8'h15, MISSION_PAY, 4, 8'd0, "CLEAR applied");
        settle;
        check(dut.trip_days_valid === 1'b0, "CLEAR forgets the trip length");
        check_letters(P_1, P_d, "display shows Id");
        check(dashes, "number shows ----");

        // =========================================================== K2
        $display("--- K2: 7-day trip in 60 ticks (fewer days than ticks), same session");
        load_commit(32'd5, 32'd65, 32'd70);
        set_days(MISSION, 32'd7, 8'd0, "7 days applied");
        cmd(8'h12, MISSION_PAY, 4, 8'd0, "ARM applied");
        cmd(8'h13, MISSION_PAY, 4, 8'd0, "START applied");
        fly(32'd5, 32'd65, 32'd7, 1'b1, 1'b0);
        check(bad_days == 0, "days to arrival equals the formula on every tick");
        check(bad_disp == 0, "display correct on every tick");
        check(dut.state == 3'd5 && dut.days_to_arrival == 32'd0, "COMPLETE, 0 days left");

        // =========================================================== K3
        $display("--- K3: 1000-day trip in 30 ticks (many days per tick); new commit forgets the old length");
        reset_board;
        seq = 0;
        cmd_detail(8'h02, 16'd0, 32'd0, {192'd0, SESSION}, 4, 8'd0, "OPEN_SESSION applied");
        load_commit(32'd5, 32'd35, 32'd40);
        set_days(MISSION, 32'd42, 8'd0, "42 days applied");
        cmd(8'h15, MISSION_PAY, 4, 8'd0, "CLEAR applied");
        load_commit(32'd5, 32'd35, 32'd40);
        check(dut.trip_days_valid === 1'b0, "new plan starts with no trip length");
        set_days(MISSION, 32'd1000, 8'd0, "1000 days applied");
        cmd(8'h12, MISSION_PAY, 4, 8'd0, "ARM applied");
        cmd(8'h13, MISSION_PAY, 4, 8'd0, "START applied");
        fly(32'd5, 32'd35, 32'd1000, 1'b1, 1'b0);
        check(bad_days == 0, "days to arrival equals the formula on every tick");
        check(bad_disp == 0, "display correct on every tick");
        check(dut.state == 3'd5 && dut.days_to_arrival == 32'd0, "COMPLETE, 0 days left");

        // =========================================================== K4
        $display("--- K4: no SET_TRIP_DAYS at all (old backend): mission still runs");
        reset_board;
        seq = 0;
        cmd_detail(8'h02, 16'd0, 32'd0, {192'd0, SESSION}, 4, 8'd0, "OPEN_SESSION applied");
        load_commit(32'd5, 32'd130, 32'd140);
        cmd(8'h12, MISSION_PAY, 4, 8'd0, "ARM applied");
        cmd(8'h13, MISSION_PAY, 4, 8'd0, "START applied");
        fly(32'd5, 32'd130, 32'd0, 1'b0, 1'b0);
        check(bad_disp == 0, "display: T-minus, then mission seconds elapsed");
        check(dut.state == 3'd5 && dut.executed_mask == 2'b11, "COMPLETE with both burns");

        // =========================================================== K5
        $display("--- K5: contracts 1.2.0 golden frames 31 / 32 / 33");
        reset_board;
        cmd_file("app/contracts/fixtures/frames/03_open_session.hex",
                 "app/contracts/fixtures/frames/04_ack_open_session.hex", "OPEN_SESSION -> golden ACK");
        cmd_file("app/contracts/fixtures/frames/06_load_plan.hex",
                 "app/contracts/fixtures/frames/07_ack_load_plan.hex", "LOAD_PLAN -> golden ACK");
        cmd_file("app/contracts/fixtures/frames/08_commit_plan.hex",
                 "app/contracts/fixtures/frames/09_ack_commit_plan.hex", "COMMIT_PLAN -> golden ACK");
        cmd_file("app/contracts/fixtures/frames/31_set_trip_days.hex",
                 "app/contracts/fixtures/frames/32_ack_set_trip_days.hex",
                 "golden SET_TRIP_DAYS (seq 3, 300 days) -> golden ACK 32, byte for byte");
        check(dut.trip_days_valid === 1'b1 && dut.trip_days == 32'd300, "trip length is 300");
        cmd_file("app/contracts/fixtures/frames/31_set_trip_days.hex",
                 "app/contracts/fixtures/frames/32_ack_set_trip_days.hex",
                 "identical retry -> the same cached ACK");

        reset_board;
        cmd_file("app/contracts/fixtures/frames/03_open_session.hex",
                 "app/contracts/fixtures/frames/04_ack_open_session.hex", "OPEN_SESSION -> golden ACK");
        cmd_file("app/contracts/fixtures/frames/06_load_plan.hex",
                 "app/contracts/fixtures/frames/07_ack_load_plan.hex", "LOAD_PLAN -> golden ACK");
        cmd_file("app/contracts/fixtures/frames/08_commit_plan.hex",
                 "app/contracts/fixtures/frames/09_ack_commit_plan.hex", "COMMIT_PLAN -> golden ACK");
        cmd_built(8'h16, 16'd3, SESSION, {160'd0, 32'd0, MISSION}, 8,
                  "app/contracts/fixtures/frames/33_nack_set_trip_days_bad_value.hex",
                  "SET_TRIP_DAYS with 0 days -> golden NACK 33, byte for byte");
        check(dut.trip_days_valid === 1'b0, "no trip length after the rejection");

        // =========================================================== K6
        $display("--- K6: plan section 19 timing (500 / 6500 / 6800), start of the countdown only");
        reset_board;
        seq = 0;
        cmd_detail(8'h02, 16'd0, 32'd0, {192'd0, SESSION}, 4, 8'd0, "OPEN_SESSION applied");
        load_commit(32'd500, 32'd6500, 32'd6800);
        set_days(MISSION, 32'd9999, 8'd0, "9999 days applied");
        cmd(8'h12, MISSION_PAY, 4, 8'd0, "ARM applied");
        cmd(8'h13, MISSION_PAY, 4, 8'd0, "START applied");
        wait_tick(32'd1);
        repeat (400) @(posedge clk);
        check(shown == 32'd499 && point, "T-minus shows 04.99 at tick 1");
        wait_tick(32'd3);
        repeat (400) @(posedge clk);
        check(shown == 32'd497 && point && dut.days_to_arrival == 32'd9999, "T-minus shows 04.97 at tick 3, days still 9999");

        check(bad_frames == 0, "every frame from the board was well formed");
        check(dut.rx_error_count == 16'd0 || dut.rx_error_count == 0, "board counted no receive errors");

        if (errors == 0) $display("SIMULATION PASS: tb_cockpit (simulation only, not a board test)");
        else             $display("SIMULATION FAIL: tb_cockpit, %0d error(s)", errors);
        $finish;
    end

endmodule
