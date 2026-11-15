// tb_heartbeat.v
// SIMULATION ONLY. Passing here does not mean the board works.
//
// Checks for the bring-up stage:
//   1. Reset asserts immediately (asynchronously) and releases on a clock edge.
//   2. The real 100 Hz divider gives exactly one pulse per 500,000 clocks.
//   3. The top level blinks LEDR0 at the expected rate (scaled-down divisors).
//   4. UART_TX idles high, LEDR9 shows reset, LEDR8..1 stay off.

`timescale 1ns / 1ps

module tb_heartbeat;

    // ---------------------------------------------------------- clock
    reg clk = 1'b0;
    always #10 clk = ~clk;           // 20 ns period = 50 MHz

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

    // ---------------------------------------------------------- DUT 1: top level, scaled down
    // 10 clocks per tick, 5 ticks per LED toggle -> LED toggles every 50 clocks.
    localparam integer TB_TICK_DIVISOR = 10;
    localparam integer TB_HALF_TICKS   = 5;
    localparam integer TOGGLE_CLOCKS   = TB_TICK_DIVISOR * TB_HALF_TICKS;

    reg  [1:0] key = 2'b11;          // buttons released
    wire [9:0] ledr;
    wire       uart_tx;

    interstellar_top #(
        .TICK_DIVISOR         (TB_TICK_DIVISOR),
        .HEARTBEAT_HALF_TICKS (TB_HALF_TICKS)
    ) dut (
        .MAX10_CLK1_50 (clk),
        .KEY           (key),
        .UART_RX       (1'b1),
        .UART_TX       (uart_tx),
        .LEDR          (ledr)
    );

    // ---------------------------------------------------------- DUT 2: real 100 Hz divider
    reg  real_rst_n = 1'b0;
    wire real_tick;

    tick_gen u_real_tick (           // default DIVISOR = 500,000
        .clk   (clk),
        .rst_n (real_rst_n),
        .tick  (real_tick)
    );

    // Count clocks between ticks and how long each tick stays high.
    integer clocks_since_tick = 0;
    integer ticks_seen        = 0;
    integer bad_periods       = 0;
    reg     real_tick_prev    = 1'b0;

    always @(posedge clk) begin
        real_tick_prev <= real_tick;
        if (real_tick) begin
            // The first tick is measured from reset release, later ones from
            // the previous tick. Both must be exactly 500,000 clocks.
            if (ticks_seen > 0 && clocks_since_tick != 500_000)
                bad_periods = bad_periods + 1;
            if (real_tick_prev)      // wider than one clock
                bad_periods = bad_periods + 1;
            ticks_seen        = ticks_seen + 1;
            clocks_since_tick = 1;
        end else begin
            clocks_since_tick = clocks_since_tick + 1;
        end
    end

    // ---------------------------------------------------------- LED toggle measurement
    integer led_clocks  = 0;
    integer led_toggles = 0;
    integer bad_toggles = 0;
    reg     led_prev    = 1'b0;
    reg     measure_led = 1'b0;

    always @(posedge clk) begin
        led_prev <= ledr[0];
        if (measure_led) begin
            if (ledr[0] != led_prev) begin
                if (led_toggles > 0 && led_clocks != TOGGLE_CLOCKS)
                    bad_toggles = bad_toggles + 1;
                led_toggles = led_toggles + 1;
                led_clocks  = 1;
            end else begin
                led_clocks = led_clocks + 1;
            end
        end
    end

    // ---------------------------------------------------------- stimulus
    initial begin
        // --- 1. Power-up: the design starts in reset, then releases itself.
        #1;
        check(ledr[9] === 1'b1, "in reset right after configuration");
        check(uart_tx === 1'b1, "UART_TX idles high during reset");
        repeat (3) @(posedge clk);
        #1;
        check(ledr[9] === 1'b0, "reset released within 3 clocks");
        check(ledr[0] === 1'b0, "heartbeat LED starts off");

        // --- 2. Heartbeat rate with scaled divisors.
        measure_led = 1'b1;
        repeat (TOGGLE_CLOCKS * 8 + 20) @(posedge clk);
        measure_led = 1'b0;
        check(led_toggles >= 8,  "LEDR0 toggled at least 8 times");
        check(bad_toggles == 0,  "every LEDR0 toggle is 50 clocks apart");
        check(ledr[8:1] === 8'b0, "LEDR8..1 stay off");
        check(uart_tx === 1'b1,   "UART_TX idles high while running");

        // --- 3. Asynchronous reset: press KEY0 between clock edges.
        @(posedge clk);
        #7 key[0] = 1'b0;            // 7 ns after the edge, not on an edge
        #1;
        check(ledr[9] === 1'b1, "reset asserts without waiting for a clock");
        check(ledr[0] === 1'b0, "heartbeat LED cleared by reset");

        // --- 4. Synchronous release: let go between edges, expect 2 clocks.
        repeat (4) @(posedge clk);
        #7 key[0] = 1'b1;
        #1;
        check(ledr[9] === 1'b1, "still in reset right after button release");
        @(posedge clk); #1;
        check(ledr[9] === 1'b1, "still in reset after 1 clock");
        @(posedge clk); #1;
        check(ledr[9] === 1'b0, "reset released on the 2nd clock edge");

        // --- 5. Real divider: exactly 500,000 clocks per 100 Hz tick.
        @(negedge clk);
        real_rst_n = 1'b1;
        repeat (500_000 * 3 + 100) @(posedge clk);
        check(ticks_seen == 3,  "3 ticks in 1,500,100 clocks at DIVISOR=500000");
        check(bad_periods == 0, "ticks are 500,000 clocks apart and 1 clock wide");

        // ---------------------------------------------------------- result
        if (errors == 0)
            $display("\nSIMULATION PASS: tb_heartbeat (simulation only, not a board test)");
        else
            $display("\nSIMULATION FAIL: tb_heartbeat, %0d error(s)", errors);
        $finish;
    end

endmodule
