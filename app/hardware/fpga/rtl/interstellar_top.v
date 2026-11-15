// interstellar_top.v
// Top level for the DE10-Lite (MAX 10 10M50DAF484C7G).
//
// Bring-up stage (issue #8, steps 1-2): reset, 100 Hz mission tick and a
// heartbeat LED. The UART pins are already placed so the wiring can be
// checked; the transmitter just idles high until the UART is added.
//
// Board controls used so far:
//   KEY0   - reset (hold to reset, release to run)
//   LEDR0  - heartbeat, blinks once per second
//   LEDR9  - on while the design is held in reset

module interstellar_top #(
    // Overridden by the testbench so simulation does not need 25 million
    // clock cycles per blink. Never changed for the real build.
    parameter integer TICK_DIVISOR         = 500_000,  // 50 MHz -> 100 Hz
    parameter integer HEARTBEAT_HALF_TICKS = 50        // 100 Hz -> 1 Hz blink
) (
    input  wire       MAX10_CLK1_50,  // 50 MHz oscillator, PIN_P11
    input  wire [1:0] KEY,            // push buttons, active low
    input  wire       UART_RX,        // from XIAO TX, JP1 pin 1, PIN_V10
    output wire       UART_TX,        // to XIAO RX,   JP1 pin 2, PIN_W10
    output wire [9:0] LEDR            // red LEDs, active high
);

    wire clk = MAX10_CLK1_50;
    wire rst_n;
    wire tick_100hz;
    wire heartbeat_led;

    reset_sync u_reset_sync (
        .clk         (clk),
        .async_rst_n (KEY[0]),
        .rst_n       (rst_n)
    );

    tick_gen #(
        .DIVISOR (TICK_DIVISOR)
    ) u_tick_100hz (
        .clk   (clk),
        .rst_n (rst_n),
        .tick  (tick_100hz)
    );

    heartbeat #(
        .HALF_PERIOD_TICKS (HEARTBEAT_HALF_TICKS)
    ) u_heartbeat (
        .clk   (clk),
        .rst_n (rst_n),
        .tick  (tick_100hz),
        .led   (heartbeat_led)
    );

    // UART line idles high. The real transmitter replaces this constant.
    assign UART_TX = 1'b1;

    assign LEDR[0]   = heartbeat_led;
    assign LEDR[8:1] = 8'b0;
    assign LEDR[9]   = ~rst_n;

endmodule
