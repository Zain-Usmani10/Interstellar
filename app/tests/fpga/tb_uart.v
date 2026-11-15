// tb_uart.v
// SIMULATION ONLY. Passing here does not mean the board works.
//
// Checks for milestone A (bytes in and out):
//   1. uart_tx -> uart_rx at the real divisor (434): bytes arrive unchanged.
//   2. A transmitted bit lasts exactly 434 clocks and the line idles high.
//   3. A byte with a bad stop bit is rejected, and the next good byte works.
//   4. A sender that is 2% fast or 2% slow is still received.
//   5. A short low glitch on the line is not taken as a byte.
//   6. Top level with TX wired to RX: LEDR1 (loopback OK) turns on and
//      LEDR2 (error) stays off; breaking the wire turns LEDR1 off.

`timescale 1ns / 1ps

module tb_uart;

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

    localparam integer BIT = 434;    // real clocks per bit

    reg rst_n = 1'b0;

    // ---------------------------------------------------------- DUT 1: tx -> rx
    reg  [7:0] tx_data  = 8'd0;
    reg        tx_start = 1'b0;
    wire       tx_line;
    wire       tx_busy;
    wire [7:0] a_data;
    wire       a_valid;
    wire       a_ferr;

    uart_tx #(.CLKS_PER_BIT(BIT)) u_tx (
        .clk(clk), .rst_n(rst_n), .data(tx_data), .start(tx_start),
        .tx(tx_line), .busy(tx_busy)
    );

    uart_rx #(.CLKS_PER_BIT(BIT)) u_rx_a (
        .clk(clk), .rst_n(rst_n), .rx(tx_line),
        .data(a_data), .valid(a_valid), .frame_error(a_ferr)
    );

    // ---------------------------------------------------------- DUT 2: rx driven by the testbench
    reg        line = 1'b1;
    wire [7:0] b_data;
    wire       b_valid;
    wire       b_ferr;

    uart_rx #(.CLKS_PER_BIT(BIT)) u_rx_b (
        .clk(clk), .rst_n(rst_n), .rx(line),
        .data(b_data), .valid(b_valid), .frame_error(b_ferr)
    );

    // Remember what each receiver reported.
    integer   a_count = 0, a_ferr_count = 0;
    integer   b_count = 0, b_ferr_count = 0;
    reg [7:0] a_last = 8'd0, b_last = 8'd0;

    always @(posedge clk) begin
        if (a_valid) begin a_count = a_count + 1; a_last = a_data; end
        if (a_ferr)  a_ferr_count = a_ferr_count + 1;
        if (b_valid) begin b_count = b_count + 1; b_last = b_data; end
        if (b_ferr)  b_ferr_count = b_ferr_count + 1;
    end

    // Send one byte through uart_tx and wait until it is done.
    task tx_send;
        input [7:0] b;
        begin
            @(negedge clk);
            tx_data  = b;
            tx_start = 1'b1;
            @(negedge clk);
            tx_start = 1'b0;
            wait (!tx_busy);
            repeat (4) @(posedge clk);
        end
    endtask

    // Drive a raw serial byte onto "line". bit_clks sets the sender's speed.
    task line_send;
        input [7:0]   b;
        input integer bit_clks;
        input         stop_bit;
        integer i;
        begin
            @(negedge clk);
            line = 1'b0;                              // start bit
            repeat (bit_clks) @(negedge clk);
            for (i = 0; i < 8; i = i + 1) begin
                line = b[i];                          // LSB first
                repeat (bit_clks) @(negedge clk);
            end
            line = stop_bit;
            repeat (bit_clks) @(negedge clk);
            line = 1'b1;                              // back to idle
            repeat (bit_clks) @(negedge clk);
        end
    endtask

    // Measure how long the start bit of a transmitted byte lasts.
    integer start_bit_clocks = 0;
    reg     measuring = 1'b0;
    always @(posedge clk) begin
        if (measuring && !tx_line)
            start_bit_clocks = start_bit_clocks + 1;
    end

    // ---------------------------------------------------------- DUT 3: top level in loopback
    reg        loop_closed = 1'b1;
    reg  [1:0] key = 2'b11;
    wire [9:0] ledr;
    wire       top_tx;
    wire       top_rx = loop_closed ? top_tx : 1'b1;

    // 16 clocks per bit -> a byte is 160 clocks; a tick every 400 clocks.
    interstellar_top #(
        .TICK_DIVISOR         (400),
        .HEARTBEAT_HALF_TICKS (5),
        .UART_CLKS_PER_BIT    (16)
    ) u_top (
        .MAX10_CLK1_50 (clk),
        .KEY           (key),
        .UART_RX       (top_rx),
        .UART_TX       (top_tx),
        .LEDR          (ledr)
    );

    integer n;

    initial begin
        repeat (5) @(posedge clk);
        rst_n = 1'b1;
        repeat (5) @(posedge clk);

        // --- 1 + 2. tx -> rx, and bit timing.
        check(tx_line === 1'b1, "TX line idles high");

        // 0xFF has only one low bit time: the start bit.
        measuring = 1'b1;
        tx_send(8'hFF);
        measuring = 1'b0;
        check(a_count == 1 && a_last == 8'hFF, "0xFF sent and received");
        check(start_bit_clocks == BIT, "start bit lasts exactly 434 clocks");

        tx_send(8'h00); check(a_count == 2 && a_last == 8'h00, "0x00 sent and received");
        tx_send(8'hA5); check(a_count == 3 && a_last == 8'hA5, "0xA5 sent and received");
        tx_send(8'h5A); check(a_count == 4 && a_last == 8'h5A, "0x5A sent and received");
        tx_send(8'h01); check(a_count == 5 && a_last == 8'h01, "0x01 sent and received (LSB first)");
        tx_send(8'h80); check(a_count == 6 && a_last == 8'h80, "0x80 sent and received (MSB last)");
        check(a_ferr_count == 0, "no framing errors on the tx -> rx path");
        check(tx_line === 1'b1, "TX line back to idle high");

        // --- 3. Bad stop bit, then recovery.
        line_send(8'h3C, BIT, 1'b0);
        check(b_count == 0,      "byte with bad stop bit is not delivered");
        check(b_ferr_count == 1, "bad stop bit is reported once");
        line_send(8'h3C, BIT, 1'b1);
        check(b_count == 1 && b_last == 8'h3C, "next good byte is received");

        // --- 4. Sender speed off by about 2%.
        line_send(8'hC3, 425, 1'b1);
        check(b_count == 2 && b_last == 8'hC3, "byte from a 2% fast sender is received");
        line_send(8'h96, 443, 1'b1);
        check(b_count == 3 && b_last == 8'h96, "byte from a 2% slow sender is received");

        // --- 5. Glitch shorter than half a bit.
        @(negedge clk); line = 1'b0;
        repeat (100) @(negedge clk);
        line = 1'b1;
        repeat (BIT * 12) @(negedge clk);
        check(b_count == 3 && b_ferr_count == 1, "short low glitch is ignored");

        // --- 6. Top-level loopback LEDs.
        // By now the top level has been running for a long time with the
        // loop closed.
        check(ledr[1] === 1'b1, "LEDR1 on with TX wired to RX");
        check(ledr[2] === 1'b0, "LEDR2 off (no loopback errors)");

        loop_closed = 1'b0;                       // pull the jumper
        repeat (400 * 40) @(posedge clk);         // 40 ticks > 25-tick hold
        check(ledr[1] === 1'b0, "LEDR1 off after the wire is removed");

        loop_closed = 1'b1;                       // put it back
        repeat (400 * 5) @(posedge clk);
        check(ledr[1] === 1'b1, "LEDR1 on again after the wire is restored");
        check(ledr[8:3] === 6'b0, "LEDR8..3 stay off");

        if (errors == 0)
            $display("\nSIMULATION PASS: tb_uart (simulation only, not a board test)");
        else
            $display("\nSIMULATION FAIL: tb_uart, %0d error(s)", errors);
        $finish;
    end

endmodule
