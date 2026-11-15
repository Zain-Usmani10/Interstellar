// tb_faults.v
// SIMULATION ONLY. Passing here does not mean the board works.
//
// Milestone D: three copies of the control tuple, the voter, and the two
// fault switches (spec section 9).
//
//   F1  SW0 (INJECT_SINGLE) mid-mission: one copy is corrupted, the vote
//       hides it, the counter goes up, the copy is repaired, and the mission
//       still completes. STATUS payload equals golden 18.
//       Also injected on the exact clock the capture burn is due.
//   F2  SW1 (INJECT_DIVERGENCE) mid-mission: all three copies differ, the
//       board latches SAFE, the capture burn never happens, the clock still
//       runs to end_tick. STATUS payload equals golden 19.
//   F3  Divergence on the exact clock the capture burn is due: no burn.
//   F4  A switch that is already up at reset does not inject anything.
//   F5  Divergence with a plan only LOADED: counted, state unchanged.
//   F6  KEY1 local abort.
//
// Test shortcuts, stated plainly: set_tick() writes the tick counter (as in
// tb_mission), and the two "exact clock" cases drive the injection pulse
// directly instead of through the switch, because a debounced switch cannot
// be timed to one clock.
//
// The monitor, senders and check tasks below are the same as in tb_mission.v.

`timescale 1ns / 1ps

module tb_faults;

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
    localparam integer DEBOUNCE = 50;    // clocks a switch must be stable (real: 500,000)

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
    reg  [1:0] sw   = 2'b00;
    reg        line = 1'b1;
    wire       tx_line;
    wire [9:0] ledr;

    interstellar_top #(
        .TICK_DIVISOR         (TICK),
        .HEARTBEAT_HALF_TICKS (50),
        .UART_CLKS_PER_BIT    (BIT),
        .FRAME_TIMEOUT_CLKS   (200_000),
        .DEBOUNCE_CLKS        (DEBOUNCE)
    ) dut (
        .MAX10_CLK1_50 (clk),
        .KEY           (key),
        .SW            (sw),
        .UART_RX       (line),
        .UART_TX       (tx_line),
        .LEDR          (ledr)
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
    wire [223:0] PLAN_PAY    = {CAP_FUEL, DEP_FUEL, INIT_FUEL, END_TICK, ARR_TICK, DEP_TICK, MISSION};

    // Reset, then open, load, commit, arm, start and wait for the departure burn.
    task start_mission;
        begin
            reset_board;
            cmd_detail(8'h02, 16'd0, 32'd0,   {192'd0, SESSION}, 4,           8'd0, "OPEN_SESSION applied");
            cmd_detail(8'h10, 16'd1, SESSION, PLAN_PAY, 28,                   8'd0, "LOAD_PLAN applied");
            cmd_detail(8'h11, 16'd2, SESSION, {176'd0, PLAN_CRC, MISSION}, 6, 8'd0, "COMMIT_PLAN applied");
            cmd_detail(8'h12, 16'd3, SESSION, MISSION_PAY, 4,                 8'd0, "ARM applied");
            cmd_detail(8'h13, 16'd4, SESSION, MISSION_PAY, 4,                 8'd0, "START applied");
            wait_tick(DEP_TICK);
            repeat (10) @(posedge clk);
        end
    endtask

    // Flip a switch up and wait for the debounced edge to take effect.
    task flip_up;
        input integer which;
        begin
            @(negedge clk);
            sw[which] = 1'b1;
            repeat (DEBOUNCE + 20) @(posedge clk);
        end
    endtask

    task flip_down;
        input integer which;
        begin
            @(negedge clk);
            sw[which] = 1'b0;
            repeat (DEBOUNCE + 20) @(posedge clk);
        end
    endtask

    // Wait for the mission tick that brings tick_count to arrival_tick. On
    // return, the current clock is the one where the capture burn is due.
    task wait_capture_due;
        begin
            set_tick(ARR_TICK - 32'd1);
            guard = 0;
            while (!dut.tick_mission && guard < 2 * TICK) begin
                @(posedge clk);
                guard = guard + 1;
            end
            @(negedge clk);
        end
    endtask

    wire lanes_equal = (dut.u_sequencer.lane_a === dut.u_sequencer.lane_b) &&
                       (dut.u_sequencer.lane_a === dut.u_sequencer.lane_c);

    initial begin
        // =========================================================== F1
        $display("--- F1: single fault is masked");
        start_mission;
        set_tick(32'd6100);
        flip_up(0);
        check(dut.masked_fault_count == 32'd1 && dut.no_majority_count == 32'd0,
              "SW0 up: exactly one masked fault counted");
        check(dut.state == 3'd3 && dut.fuel_g == CAP_FUEL && dut.executed_mask == 2'b01,
              "mission still RUNNING with the correct fuel");
        check(lanes_equal, "corrupted copy was repaired (all three copies equal again)");
        check_status_equals("app/contracts/fixtures/frames/18_status_running_single_fault_masked.hex",
                            "STATUS payload equals golden 18 (single fault masked)");
        check(ledr[6] === 1'b1 && ledr[2] === 1'b1, "fault LED on, RUNNING LED still on");
        flip_down(0);
        check(dut.masked_fault_count == 32'd1, "switching SW0 back down injects nothing");

        wait_capture_due;
        check(dut.tick_count == ARR_TICK && dut.state == 3'd3, "capture burn is due on this clock");
        force dut.inject_single = 1'b1;
        @(negedge clk);
        release dut.inject_single;
        check(dut.state == 3'd3 && dut.executed_mask == 2'b01,
              "burn is held back one clock while the fault is voted");
        repeat (4) @(posedge clk);
        check(dut.state == 3'd5 && dut.executed_mask == 2'b11 && dut.fuel_g == 32'd0 &&
              dut.capture_executed_tick == ARR_TICK,
              "single fault at the event boundary: capture still executes at tick 12010");
        check(dut.masked_fault_count == 32'd2 && lanes_equal, "second fault counted and repaired");

        // =========================================================== F2
        $display("--- F2: divergence latches SAFE");
        start_mission;
        set_tick(32'd7000);
        flip_up(1);
        check(dut.no_majority_count == 32'd1 && dut.masked_fault_count == 32'd0,
              "SW1 up: exactly one no-majority event counted");
        check(dut.state == 3'd4 && dut.safe_reason == 3'd1, "board is SAFE, reason NO_MAJORITY");
        check(dut.fuel_g == CAP_FUEL && dut.executed_mask == 2'b01 && dut.departure_executed_tick == DEP_TICK,
              "fuel and departure record kept from the last good value");
        check(lanes_equal, "all three copies rewritten to SAFE");
        check_status_equals("app/contracts/fixtures/frames/19_status_safe_no_majority.hex",
                            "STATUS payload equals golden 19 (SAFE, no majority)");
        check(ledr[4] === 1'b1 && ledr[6] === 1'b1, "SAFE LED and fault LED on");

        set_tick(ARR_TICK - 32'd3);
        repeat (6 * TICK) @(posedge clk);
        check(dut.state == 3'd4 && dut.executed_mask == 2'b01 && dut.fuel_g == CAP_FUEL &&
              dut.capture_executed_tick == 32'hFFFFFFFF,
              "capture burn did not happen in SAFE");
        check(dut.tick_count > ARR_TICK, "mission clock kept running in SAFE");
        set_tick(END_TICK - 32'd3);
        repeat (6 * TICK) @(posedge clk);
        check(dut.tick_count == END_TICK, "clock stops at end_tick");

        cmd_detail(8'h14, 16'd5, SESSION, MISSION_PAY, 4, 8'd0, "ABORT from SAFE applied");
        check(dut.state == 3'd6, "state ABORTED");
        cmd_detail(8'h15, 16'd6, SESSION, MISSION_PAY, 4, 8'd0, "CLEAR applied");
        check(dut.state == 3'd0 && dut.no_majority_count == 32'd1, "IDLE; fault counter survives CLEAR");

        // =========================================================== F4
        $display("--- F4: switch already up at reset");
        sw = 2'b11;
        reset_board;
        repeat (DEBOUNCE * 3) @(posedge clk);
        check(dut.masked_fault_count == 32'd0 && dut.no_majority_count == 32'd0,
              "switches up at reset inject nothing");
        check(ledr[6] === 1'b0, "fault LED off after reset");
        flip_down(0);
        flip_up(0);
        check(dut.masked_fault_count == 32'd1, "a real flip after reset is counted");
        flip_down(0);
        flip_down(1);

        // =========================================================== F3
        $display("--- F3: divergence on the clock the capture burn is due");
        start_mission;
        wait_capture_due;
        check(dut.tick_count == ARR_TICK && dut.state == 3'd3, "capture burn is due on this clock");
        force dut.inject_divergence = 1'b1;
        @(negedge clk);
        release dut.inject_divergence;
        repeat (4) @(posedge clk);
        check(dut.state == 3'd4 && dut.safe_reason == 3'd1, "SAFE, reason NO_MAJORITY");
        check(dut.executed_mask == 2'b01 && dut.fuel_g == CAP_FUEL &&
              dut.capture_executed_tick == 32'hFFFFFFFF,
              "capture burn suppressed, fuel untouched");
        repeat (3 * TICK) @(posedge clk);
        check(dut.executed_mask == 2'b01 && dut.state == 3'd4, "missed capture is not re-fired later");

        // =========================================================== F5
        $display("--- F5: divergence with a plan only LOADED");
        reset_board;
        cmd_detail(8'h02, 16'd0, 32'd0,   {192'd0, SESSION}, 4,           8'd0, "OPEN_SESSION applied");
        cmd_detail(8'h10, 16'd1, SESSION, PLAN_PAY, 28,                   8'd0, "LOAD_PLAN applied");
        cmd_detail(8'h11, 16'd2, SESSION, {176'd0, PLAN_CRC, MISSION}, 6, 8'd0, "COMMIT_PLAN applied");
        flip_up(1);
        check(dut.no_majority_count == 32'd1 && dut.state == 3'd1 && dut.fuel_g == INIT_FUEL,
              "counted, state still LOADED, fuel intact");
        flip_down(1);
        cmd_detail(8'h12, 16'd3, SESSION, MISSION_PAY, 4, 8'd0, "ARM still works afterwards");

        // =========================================================== F6
        $display("--- F6: KEY1 local abort");
        cmd_detail(8'h13, 16'd4, SESSION, MISSION_PAY, 4, 8'd0, "START applied");
        @(negedge clk); key[1] = 1'b0;
        repeat (DEBOUNCE + 20) @(posedge clk);
        @(negedge clk); key[1] = 1'b1;
        repeat (DEBOUNCE + 20) @(posedge clk);
        check(dut.state == 3'd6, "KEY1 while RUNNING -> ABORTED");

        check(bad_frames == 0, "every frame the board sent was well formed with a good CRC");

        if (errors == 0)
            $display("\nSIMULATION PASS: tb_faults (simulation only, not a board test)");
        else
            $display("\nSIMULATION FAIL: tb_faults, %0d error(s)", errors);
        $finish;
    end

endmodule
