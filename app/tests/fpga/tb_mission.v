// tb_mission.v
// SIMULATION ONLY. Passing here does not mean the board works.
//
// Milestone C: commands and the mission, checked against the golden frames
// in app/contracts/fixtures/frames/ (run from the repo root, see run_sim.sh).
//
//   Scenario 1  open, load, commit, arm, start, departure burn, abort,
//               coast to end_tick, clear. Every ACK byte for byte.
//   Scenario 2  the same start, then run to the capture burn and COMPLETE.
//   Scenario 3  rejections: bad plan, bad plan CRC, bad state, bad session,
//               stale sequence, sequence conflict, bad mission, and an
//               exact retry that must not be applied twice.
//
// STATUS frames are compared on session and payload (mission, tick, state,
// fuel, events...). Their telemetry sequence number is not compared because
// it depends on how many STATUS frames were sent before.
//
// Test shortcut, stated plainly: to avoid simulating two minutes of mission
// time, set_tick() writes the board's tick counter directly to just before
// the moment being tested. The burns themselves still fire from the real
// counter reaching the real plan values.

`timescale 1ns / 1ps

module tb_mission;

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

    interstellar_top #(
        .TICK_DIVISOR         (TICK),
        .HEARTBEAT_HALF_TICKS (50),
        .UART_CLKS_PER_BIT    (BIT),
        .FRAME_TIMEOUT_CLKS   (200_000)
    ) dut (
        .MAX10_CLK1_50 (clk),
        .KEY           (key),
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

    // open session, load, commit: the common start of every scenario
    task open_load_commit;
        begin
            cmd_file("app/contracts/fixtures/frames/03_open_session.hex",
                     "app/contracts/fixtures/frames/04_ack_open_session.hex",
                     "OPEN_SESSION -> golden ACK");
            cmd_file("app/contracts/fixtures/frames/06_load_plan.hex",
                     "app/contracts/fixtures/frames/07_ack_load_plan.hex",
                     "LOAD_PLAN -> golden ACK (plan CRC computed on the board)");
            cmd_file("app/contracts/fixtures/frames/08_commit_plan.hex",
                     "app/contracts/fixtures/frames/09_ack_commit_plan.hex",
                     "COMMIT_PLAN -> golden ACK");
        end
    endtask

    task arm_start;
        begin
            cmd_file("app/contracts/fixtures/frames/11_arm.hex",
                     "app/contracts/fixtures/frames/12_ack_arm.hex",
                     "ARM -> golden ACK");
            cmd_file("app/contracts/fixtures/frames/13_start.hex",
                     "app/contracts/fixtures/frames/14_ack_start.hex",
                     "START -> golden ACK");
        end
    endtask

    reg [7:0] saved_ack [0:63];
    wire [223:0] MISSION_PAY = {192'd0, MISSION};

    initial begin
        // =========================================================== Scenario 1
        $display("--- scenario 1: abort after departure, coast, clear");
        reset_board;
        open_load_commit;
        check_status_equals("app/contracts/fixtures/frames/10_status_loaded.hex",
                            "STATUS payload equals golden 10 (LOADED)");
        check(ledr[1] === 1'b1 && ledr[7] === 1'b1, "READY and session LEDs on");

        arm_start;
        check(ledr[2] === 1'b1, "RUNNING LED on");

        wait_tick(32'd5);
        check_status_equals("app/contracts/fixtures/frames/15_status_running_before_departure.hex",
                            "STATUS payload equals golden 15 (tick 5, before departure)");

        wait_tick(DEP_TICK);
        repeat (10) @(posedge clk);
        check(dut.executed_mask == 2'b01 && dut.fuel_g == CAP_FUEL &&
              dut.departure_executed_tick == DEP_TICK,
              "departure burn fired at tick 10 and fuel was deducted once");

        set_tick(32'd6000);
        check_status_equals("app/contracts/fixtures/frames/16_status_running_after_departure.hex",
                            "STATUS payload equals golden 16 (tick 6000, after departure)");

        set_tick(32'd7200);
        cmd_file("app/contracts/fixtures/frames/20_abort.hex",
                 "app/contracts/fixtures/frames/21_ack_abort.hex",
                 "ABORT at tick 7200 -> golden ACK (applied_tick 7200)");
        check(ledr[5] === 1'b1, "ABORTED LED on");

        set_tick(32'd7250);
        check_status_equals("app/contracts/fixtures/frames/22_status_aborted.hex",
                            "STATUS payload equals golden 22 (ABORTED, clock still running)");

        set_tick(END_TICK - 32'd5);
        repeat (8 * TICK) @(posedge clk);
        check(dut.tick_count == END_TICK, "aborted mission coasts to end_tick");
        repeat (3 * TICK) @(posedge clk);
        check(dut.tick_count == END_TICK && dut.state == 3'd6, "clock stops at end_tick, still ABORTED");
        check(dut.executed_mask == 2'b01 && dut.fuel_g == CAP_FUEL, "no capture burn after abort");

        cmd_file("app/contracts/fixtures/frames/23_clear.hex",
                 "app/contracts/fixtures/frames/24_ack_clear.hex",
                 "CLEAR -> golden ACK");
        check(dut.state == 3'd0 && dut.plan_valid == 1'b0 && dut.tick_count == 32'd0,
              "after CLEAR: IDLE, no plan, tick 0");

        // =========================================================== Scenario 2
        $display("--- scenario 2: full mission to COMPLETE");
        reset_board;
        open_load_commit;
        arm_start;
        wait_tick(DEP_TICK);
        set_tick(ARR_TICK - 32'd5);
        check(dut.state == 3'd3 && dut.executed_mask == 2'b01, "still RUNNING just before arrival");
        repeat (7 * TICK) @(posedge clk);
        check(dut.state == 3'd5 && dut.tick_count == ARR_TICK, "capture burn at tick 12010 -> COMPLETE");
        repeat (3 * TICK) @(posedge clk);
        check_status_equals("app/contracts/fixtures/frames/17_status_complete.hex",
                            "STATUS payload equals golden 17 (COMPLETE, clock stopped, fuel 0)");
        check(ledr[3] === 1'b1, "COMPLETE LED on");

        // =========================================================== Scenario 3
        $display("--- scenario 3: rejections and retries");
        reset_board;
        cmd_detail(8'h12, 16'd1, SESSION, MISSION_PAY, 4, 8'd3, "ARM before any session -> BAD_SESSION");
        cmd_file("app/contracts/fixtures/frames/03_open_session.hex",
                 "app/contracts/fixtures/frames/04_ack_open_session.hex",
                 "OPEN_SESSION -> golden ACK");
        // Plan with arrival_tick <= departure_tick.
        cmd_built(8'h10, 16'd1, SESSION,
                  {CAP_FUEL, DEP_FUEL, INIT_FUEL, END_TICK, DEP_TICK, DEP_TICK, MISSION}, 28,
                  "app/contracts/fixtures/frames/30_nack_load_bad_plan.hex",
                  "LOAD_PLAN with a bad plan -> golden NACK 30 (BAD_PLAN)");
        // Plan whose burns cost more than the starting fuel.
        cmd_detail(8'h10, 16'd2, SESSION,
                   {CAP_FUEL, DEP_FUEL, INIT_FUEL - 32'd1, END_TICK, ARR_TICK, DEP_TICK, MISSION}, 28,
                   8'd4, "LOAD_PLAN with too little fuel -> BAD_PLAN");

        reset_board;
        cmd_file("app/contracts/fixtures/frames/03_open_session.hex",
                 "app/contracts/fixtures/frames/04_ack_open_session.hex",
                 "OPEN_SESSION -> golden ACK");
        cmd_file("app/contracts/fixtures/frames/06_load_plan.hex",
                 "app/contracts/fixtures/frames/07_ack_load_plan.hex",
                 "LOAD_PLAN -> golden ACK");
        cmd_built(8'h11, 16'd2, SESSION, {176'd0, PLAN_CRC ^ 16'h0001, MISSION}, 6,
                  "app/contracts/fixtures/frames/29_nack_commit_bad_plan_crc.hex",
                  "COMMIT_PLAN with a wrong CRC -> golden NACK 29 (BAD_PLAN_CRC)");
        check(dut.state == 3'd0, "plan did not become active");

        reset_board;
        open_load_commit;
        cmd_built(8'h13, 16'd3, SESSION, MISSION_PAY, 4,
                  "app/contracts/fixtures/frames/25_nack_start_bad_state.hex",
                  "START while LOADED -> golden NACK 25 (BAD_STATE)");
        cmd_built(8'h12, 16'd3, 32'h11111111, MISSION_PAY, 4,
                  "app/contracts/fixtures/frames/26_nack_arm_bad_session.hex",
                  "ARM with a wrong session -> golden NACK 26 (BAD_SESSION)");
        cmd_built(8'h12, 16'd2, SESSION, MISSION_PAY, 4,
                  "app/contracts/fixtures/frames/27_nack_arm_stale_seq.hex",
                  "ARM with an old sequence -> golden NACK 27 (STALE_SEQ)");
        cmd_built(8'h12, 16'd3, SESSION, MISSION_PAY, 4,
                  "app/contracts/fixtures/frames/28_nack_arm_seq_conflict.hex",
                  "ARM reusing sequence 3 -> golden NACK 28 (SEQ_CONFLICT)");
        cmd_built(8'h13, 16'd3, SESSION, MISSION_PAY, 4,
                  "app/contracts/fixtures/frames/25_nack_start_bad_state.hex",
                  "exact retry of the rejected START -> same NACK 25 again");
        check(dut.state == 3'd1, "state is still LOADED after all rejections");

        cmd_detail(8'h12, 16'd4, SESSION, {192'd0, MISSION + 32'd1}, 4, 8'd2, "ARM for another mission -> BAD_MISSION");
        cmd_detail(8'h12, 16'd5, SESSION, MISSION_PAY, 4, 8'd0, "ARM sequence 5 -> APPLIED");
        cmd_detail(8'h13, 16'd6, SESSION, MISSION_PAY, 4, 8'd0, "START sequence 6 -> APPLIED");
        for (i = 0; i < 30; i = i + 1) saved_ack[i] = ack[i];

        wait_tick(32'd3);
        n0 = ack_count;
        send_frame(8'h13, 16'd6, SESSION, MISSION_PAY, 4);          // lost-ACK retry
        wait_ack;
        match = (ack_count != n0);
        for (i = 0; i < 30; i = i + 1)
            if (ack[i] !== saved_ack[i]) match = 0;
        check(match, "exact retry of START returns the identical ACK");
        check(dut.state == 3'd3 && dut.tick_count >= 32'd3, "retry did not restart the mission clock");

        cmd_detail(8'h02, 16'd0, 32'd0, {192'd0, 32'h55667788}, 4, 8'd1, "OPEN_SESSION while RUNNING -> BAD_STATE");
        cmd_detail(8'h15, 16'd7, SESSION, MISSION_PAY, 4, 8'd1, "CLEAR while RUNNING -> BAD_STATE");
        cmd_detail(8'h10, 16'd8, SESSION,
                   {CAP_FUEL, DEP_FUEL, INIT_FUEL, END_TICK, ARR_TICK, DEP_TICK, MISSION}, 28,
                   8'd1, "LOAD_PLAN while RUNNING -> BAD_STATE");
        check(dut.state == 3'd3, "mission still RUNNING");

        check(bad_frames == 0, "every frame the board sent was well formed with a good CRC");
        check(dut.rx_error_count == 32'd0, "board counted no receive errors");

        if (errors == 0)
            $display("\nSIMULATION PASS: tb_mission (simulation only, not a board test)");
        else
            $display("\nSIMULATION FAIL: tb_mission, %0d error(s)", errors);
        $finish;
    end

endmodule
