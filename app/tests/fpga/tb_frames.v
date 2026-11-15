// tb_frames.v
// SIMULATION ONLY. Passing here does not mean the board works.
//
// Milestone B: frames and STATUS, checked against the golden fixtures in
// app/contracts/fixtures/frames/ (run from the repo root, see run_sim.sh).
//
//   1. DISCOVER in -> STATUS out, byte for byte equal to the golden frame.
//   2. GET_STATUS -> STATUS with the next telemetry sequence and a good CRC.
//   3. The five invalid frames (40-44) get no reply and are each counted.
//   4. The four messy byte streams (50-53) recover the frames they hide.
//   5. A frame left unfinished is dropped after the timeout.
//
// The 100 Hz tick is slowed right down here so the periodic 10 Hz STATUS
// never fires and every reply seen is an answer to a request.

`timescale 1ns / 1ps

module tb_frames;

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

    // Fast settings so a 54-byte frame takes about 4,300 clocks.
    localparam integer BIT     = 8;         // clocks per UART bit
    localparam integer TIMEOUT = 20_000;    // clocks, stands in for 100 ms

    // ---------------------------------------------------------- DUT 1: driven by the testbench
    reg  [1:0] key  = 2'b11;
    reg        line = 1'b1;      // into UART_RX
    wire       tx_line;          // out of UART_TX
    wire [9:0] ledr;

    interstellar_top #(
        .TICK_DIVISOR         (100_000_000),
        .HEARTBEAT_HALF_TICKS (5),
        .UART_CLKS_PER_BIT    (BIT),
        .FRAME_TIMEOUT_CLKS   (TIMEOUT)
    ) dut (
        .MAX10_CLK1_50 (clk),
        .KEY           (key),
        .UART_RX       (line),
        .UART_TX       (tx_line),
        .LEDR          (ledr)
    );

    // Monitor: collect every byte the board transmits.
    reg        mon_rst_n = 1'b0;
    wire [7:0] mon_data;
    wire       mon_valid;
    wire       mon_ferr;

    uart_rx #(.CLKS_PER_BIT(BIT)) u_monitor (
        .clk(clk), .rst_n(mon_rst_n), .rx(tx_line),
        .data(mon_data), .valid(mon_valid), .frame_error(mon_ferr)
    );

    reg [7:0] got [0:255];
    integer   got_n = 0;
    integer   mon_ferr_count = 0;

    always @(posedge clk) begin
        if (mon_valid) begin
            got[got_n] = mon_data;
            got_n = got_n + 1;
        end
        if (mon_ferr) mon_ferr_count = mon_ferr_count + 1;
    end

    // Count good command frames accepted by the frame receiver.
    integer good_frames = 0;
    always @(posedge clk) begin
        if (dut.frame_valid) good_frames = good_frames + 1;
    end

    // ---------------------------------------------------------- fixture files
    reg [7:0] file_mem [0:255];
    integer   file_n;
    reg [7:0] exp_mem [0:255];
    integer   exp_n;
    integer   i;

    task load_file;                 // into file_mem / file_n
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

    task load_expected;             // into exp_mem / exp_n
        input [1023:0] path;
        begin
            for (i = 0; i < 256; i = i + 1) exp_mem[i] = 8'hxx;
            $readmemh(path, exp_mem);
            exp_n = 0;
            while (exp_n < 256 && exp_mem[exp_n] !== 8'hxx) exp_n = exp_n + 1;
        end
    endtask

    // ---------------------------------------------------------- sending bytes
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

    // Send bytes [first, last) of the loaded file.
    task send_range;
        input integer first;
        input integer last;
        integer n;
        begin
            for (n = first; n < last; n = n + 1) send_byte(file_mem[n]);
        end
    endtask

    // Load a fixture, forget earlier replies, send it, wait for any reply.
    task send_fixture;
        input [1023:0] path;
        begin
            load_file(path);
            got_n = 0;
            send_range(0, file_n);
            repeat (BIT * 10 * 70) @(posedge clk);   // longer than a 54-byte reply
        end
    endtask

    // ---------------------------------------------------------- checking a STATUS reply
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

    reg [15:0] crc_calc;
    reg [15:0] reply_seq;
    reg [31:0] reply_rx_errors;
    reg        reply_ok;

    // Decode what is in got[]. Sets reply_ok, reply_seq, reply_rx_errors.
    task decode_status;
        begin
            reply_ok = (got_n == 54) && got[0] == 8'hA5 && got[1] == 8'h5A &&
                       got[2] == 8'h01 && got[3] == 8'h81 &&
                       got[10] == 8'd40 && got[11] == 8'd0;
            crc_calc = 16'hFFFF;
            if (got_n == 54) begin
                for (i = 2; i < 52; i = i + 1) crc_calc = crc_step(crc_calc, got[i]);
                if (got[52] !== crc_calc[7:0] || got[53] !== crc_calc[15:8]) reply_ok = 1'b0;
                reply_seq       = {got[5], got[4]};
                reply_rx_errors = {got[47], got[46], got[45], got[44]};   // payload bytes 32..35
            end else begin
                reply_seq       = 16'hxxxx;
                reply_rx_errors = 32'hxxxxxxxx;
            end
        end
    endtask

    integer match;
    integer before;

    initial begin
        repeat (10) @(posedge clk);
        mon_rst_n = 1'b1;
        repeat (10) @(posedge clk);

        // --- 1. DISCOVER -> golden STATUS after reset.
        send_fixture("app/contracts/fixtures/frames/01_discover.hex");
        load_expected("app/contracts/fixtures/frames/02_status_after_reset.hex");
        check(exp_n == 54, "golden STATUS fixture has 54 bytes");
        match = (got_n == exp_n);
        for (i = 0; i < exp_n; i = i + 1)
            if (got[i] !== exp_mem[i]) match = 0;
        check(match, "DISCOVER reply equals 02_status_after_reset byte for byte");
        check(good_frames == 1, "one good command frame counted");

        // --- 2. GET_STATUS -> next telemetry sequence.
        send_fixture("app/contracts/fixtures/frames/05_get_status.hex");
        decode_status;
        check(reply_ok, "GET_STATUS reply is a STATUS frame with a good CRC");
        check(reply_seq == 16'd1, "telemetry sequence went from 0 to 1");
        check(reply_rx_errors == 32'd0, "no receive errors so far");

        // --- 3. Invalid frames: no reply, each counted once.
        send_fixture("app/contracts/fixtures/frames/40_invalid_bad_crc.hex");
        check(got_n == 0, "40 bad CRC: no reply");
        send_fixture("app/contracts/fixtures/frames/41_invalid_bad_version.hex");
        check(got_n == 0, "41 bad version: no reply");
        send_fixture("app/contracts/fixtures/frames/42_invalid_oversize_length.hex");
        check(got_n == 0, "42 oversize length: no reply");
        send_fixture("app/contracts/fixtures/frames/43_invalid_wrong_length_for_type.hex");
        check(got_n == 0, "43 wrong length for type: no reply");
        send_fixture("app/contracts/fixtures/frames/44_invalid_unknown_type.hex");
        check(got_n == 0, "44 unknown type: no reply");
        check(good_frames == 2, "invalid frames were not counted as good");

        send_fixture("app/contracts/fixtures/frames/05_get_status.hex");
        decode_status;
        check(reply_ok && reply_seq == 16'd2, "board still answers after the invalid frames");
        check(reply_rx_errors == 32'd5, "rx_error_count is 5 after five invalid frames");

        // --- 4. Messy streams.
        send_fixture("app/contracts/fixtures/frames/50_stream_garbage_then_valid.hex");
        decode_status;
        check(reply_ok && reply_seq == 16'd3, "50 garbage then valid: GET_STATUS recovered");
        check(reply_rx_errors == 32'd6, "50: the false frame start was counted");

        before = good_frames;
        send_fixture("app/contracts/fixtures/frames/51_stream_two_frames.hex");
        check(good_frames == before + 2, "51 two frames back to back: both received");

        send_fixture("app/contracts/fixtures/frames/52_stream_bad_crc_then_valid.hex");
        decode_status;
        check(reply_ok && reply_seq == 16'd4, "52 bad CRC then valid: GET_STATUS recovered");
        check(reply_rx_errors == 32'd7, "52: the bad CRC frame was counted");

        send_fixture("app/contracts/fixtures/frames/53_stream_truncated_then_valid.hex");
        decode_status;
        check(reply_ok && reply_seq == 16'd5, "53 truncated then valid: GET_STATUS recovered");
        check(reply_rx_errors == 32'd8, "53: the truncated frame was counted");

        // --- 5. Unfinished frame, then silence longer than the timeout.
        load_file("app/contracts/fixtures/frames/11_arm.hex");
        got_n = 0;
        send_range(0, 9);                          // first 9 bytes only
        repeat (TIMEOUT + 5000) @(posedge clk);
        check(got_n == 0, "unfinished frame: no reply");
        send_fixture("app/contracts/fixtures/frames/05_get_status.hex");
        decode_status;
        check(reply_ok && reply_seq == 16'd6, "GET_STATUS answered after the timeout");
        check(reply_rx_errors == 32'd9, "the timed-out frame was counted");
        check(mon_ferr_count == 0, "every transmitted byte had a good stop bit");

        if (errors == 0)
            $display("\nSIMULATION PASS: tb_frames (simulation only, not a board test)");
        else
            $display("\nSIMULATION FAIL: tb_frames, %0d error(s)", errors);
        $finish;
    end

endmodule
