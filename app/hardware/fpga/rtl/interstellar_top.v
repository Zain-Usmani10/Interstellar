// interstellar_top.v
// Top level for the DE10-Lite (MAX 10 10M50DAF484C7G).
// This is the only file that connects modules to each other and to pins.
//
// Bring-up stage (issue #8, milestone A): reset, 100 Hz mission tick,
// heartbeat, UART receiver and transmitter with a loopback self-check.
//
// Board controls used so far:
//   KEY0   - reset (hold to reset, release to run)
//   LEDR0  - heartbeat, blinks once per second
//   LEDR1  - UART loopback OK (on while sent bytes come back correctly)
//   LEDR2  - UART error seen (stays on until reset)
//   LEDR9  - on while the design is held in reset

module interstellar_top #(
    // Overridden by testbenches so simulation runs fast. Never changed for
    // the real build.
    parameter integer TICK_DIVISOR         = 500_000,  // 50 MHz -> 100 Hz
    parameter integer HEARTBEAT_HALF_TICKS = 50,       // 100 Hz -> 1 Hz blink
    parameter integer UART_CLKS_PER_BIT    = 434       // 50 MHz -> 115200 baud
) (
    input  wire       MAX10_CLK1_50,  // 50 MHz oscillator, PIN_P11
    input  wire [1:0] KEY,            // push buttons, active low
    input  wire       UART_RX,        // JP1 pin 1, PIN_V10
    output wire       UART_TX,        // JP1 pin 2, PIN_W10
    output wire [9:0] LEDR            // red LEDs, active high
);

    wire clk = MAX10_CLK1_50;
    wire rst_n;
    wire tick_100hz;
    wire heartbeat_led;

    // ------------------------------------------------------------ reset, tick, heartbeat
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

    // ------------------------------------------------------------ UART
    wire [7:0] rx_data;
    wire       rx_valid;
    wire       rx_frame_error;

    wire [7:0] tx_data;
    wire       tx_start;
    wire       tx_busy;

    uart_rx #(
        .CLKS_PER_BIT (UART_CLKS_PER_BIT)
    ) u_uart_rx (
        .clk         (clk),
        .rst_n       (rst_n),
        .rx          (UART_RX),
        .data        (rx_data),
        .valid       (rx_valid),
        .frame_error (rx_frame_error)
    );

    uart_tx #(
        .CLKS_PER_BIT (UART_CLKS_PER_BIT)
    ) u_uart_tx (
        .clk   (clk),
        .rst_n (rst_n),
        .data  (tx_data),
        .start (tx_start),
        .tx    (UART_TX),
        .busy  (tx_busy)
    );

    // ------------------------------------------------------------ loopback self-check (temporary)
    wire loopback_ok;
    wire loopback_err;

    uart_loopback_check u_loopback (
        .clk            (clk),
        .rst_n          (rst_n),
        .tick           (tick_100hz),
        .tx_busy        (tx_busy),
        .tx_data        (tx_data),
        .tx_start       (tx_start),
        .rx_data        (rx_data),
        .rx_valid       (rx_valid),
        .rx_frame_error (rx_frame_error),
        .ok_led         (loopback_ok),
        .err_led        (loopback_err)
    );

    // ------------------------------------------------------------ LEDs
    assign LEDR[0]   = heartbeat_led;
    assign LEDR[1]   = loopback_ok;
    assign LEDR[2]   = loopback_err;
    assign LEDR[8:3] = 6'b0;
    assign LEDR[9]   = ~rst_n;

endmodule
