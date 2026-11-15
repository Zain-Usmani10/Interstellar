// interstellar_top.v
// Top level for the DE10-Lite (MAX 10 10M50DAF484C7G).
// This is the only file that connects modules to each other and to pins.
//
// Stage (issue #8, milestone B): reset, 100 Hz mission tick, heartbeat,
// UART, protocol v1 frame receiver and sender. DISCOVER and GET_STATUS are
// answered with a STATUS frame. The mission fields in STATUS are still the
// fixed after-reset values; the mission logic arrives in milestone C.
//
// Board controls used so far:
//   KEY0   - reset (hold to reset, release to run)
//   KEY1   - bring-up self-test: send a DISCOVER frame out of UART_TX
//   LEDR0  - heartbeat, blinks once per second
//   LEDR1  - flips each time a good command frame is received
//   LEDR2  - flips each time a received frame is dropped (error count bit 0)
//   LEDR9  - on while the design is held in reset

module interstellar_top #(
    // Overridden by testbenches so simulation runs fast. Never changed for
    // the real build.
    parameter integer TICK_DIVISOR         = 500_000,    // 50 MHz -> 100 Hz
    parameter integer HEARTBEAT_HALF_TICKS = 50,         // 100 Hz -> 1 Hz blink
    parameter integer UART_CLKS_PER_BIT    = 434,        // 50 MHz -> 115200 baud
    parameter integer FRAME_TIMEOUT_CLKS   = 5_000_000,  // 100 ms
    parameter integer DEBOUNCE_CLKS        = 500_000     // 10 ms
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

    // ------------------------------------------------------------ UART bytes
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

    // ------------------------------------------------------------ frames in
    wire         frame_valid;
    wire [7:0]   frame_type;
    wire [15:0]  frame_seq;
    wire [31:0]  frame_session;
    wire [223:0] frame_payload;
    wire [31:0]  rx_error_count;

    frame_rx #(
        .TIMEOUT_CLKS (FRAME_TIMEOUT_CLKS)
    ) u_frame_rx (
        .clk            (clk),
        .rst_n          (rst_n),
        .rx_data        (rx_data),
        .rx_valid       (rx_valid),
        .rx_frame_error (rx_frame_error),
        .frame_valid    (frame_valid),
        .frame_type     (frame_type),
        .frame_seq      (frame_seq),
        .frame_session  (frame_session),
        .frame_payload  (frame_payload),
        .error_count    (rx_error_count)
    );

    // DISCOVER (0x01) and GET_STATUS (0x03) are answered with STATUS.
    wire status_req = frame_valid && (frame_type == 8'h01 || frame_type == 8'h03);

    // ------------------------------------------------------------ frames out
    wire         ftx_busy;
    wire         st_start,  self_start;
    wire [7:0]   st_type,   self_type;
    wire [15:0]  st_seq,    self_seq;
    wire [31:0]  self_session;
    wire [319:0] st_payload, self_payload;
    wire [7:0]   st_len,    self_len;
    wire         st_pending;

    // The board's active session. 0 until OPEN_SESSION exists (milestone C).
    wire [31:0]  active_session = 32'd0;

    // Free = idle and nobody started a frame on this clock.
    wire ftx_free = !ftx_busy && !st_start && !self_start;

    status_gen u_status_gen (
        .clk                     (clk),
        .rst_n                   (rst_n),
        .send_req                (status_req),
        .tx_free                 (ftx_free),
        // After-reset values until the mission logic exists (milestone C).
        .mission_id              (32'd0),
        .tick                    (32'd0),
        .state                   (8'd0),            // IDLE
        .executed_mask           (8'd0),
        .safe_reason             (8'd0),
        .fuel_remaining_g        (32'd0),
        .departure_executed_tick (32'hFFFF_FFFF),   // not executed
        .capture_executed_tick   (32'hFFFF_FFFF),   // not executed
        .masked_fault_count      (32'd0),
        .no_majority_count       (32'd0),
        .rx_error_count          (rx_error_count),
        .plan_crc16              (16'd0),
        .tx_start                (st_start),
        .tx_type                 (st_type),
        .tx_seq                  (st_seq),
        .tx_payload              (st_payload),
        .tx_len                  (st_len),
        .pending                 (st_pending)
    );

    // ------------------------------------------------------------ KEY1 self-test (bring-up)
    wire key1_pressed;
    wire selftest_led;

    debounce #(
        .STABLE_CLKS (DEBOUNCE_CLKS),
        .IDLE_LEVEL  (1'b1)
    ) u_key1 (
        .clk   (clk),
        .rst_n (rst_n),
        .raw   (KEY[1]),
        .level (),
        .rose  (),
        .fell  (key1_pressed)       // keys are active low: press = falling
    );

    bringup_selftest u_selftest (
        .clk         (clk),
        .rst_n       (rst_n),
        .key_pressed (key1_pressed),
        .tx_free     (ftx_free && !st_pending),   // replies go first
        .frame_valid (frame_valid),
        .tx_start    (self_start),
        .tx_type     (self_type),
        .tx_seq      (self_seq),
        .tx_session  (self_session),
        .tx_payload  (self_payload),
        .tx_len      (self_len),
        .good_led    (selftest_led)
    );

    // One transmitter, two possible senders. Only one starts at a time.
    frame_tx u_frame_tx (
        .clk         (clk),
        .rst_n       (rst_n),
        .start       (st_start | self_start),
        .msg_type    (self_start ? self_type    : st_type),
        .seq         (self_start ? self_seq     : st_seq),
        .session     (self_start ? self_session : active_session),
        .payload     (self_start ? self_payload : st_payload),
        .payload_len (self_start ? self_len     : st_len),
        .busy        (ftx_busy),
        .tx_busy     (tx_busy),
        .tx_data     (tx_data),
        .tx_start    (tx_start)
    );

    // ------------------------------------------------------------ LEDs
    assign LEDR[0]   = heartbeat_led;
    assign LEDR[1]   = selftest_led;
    assign LEDR[2]   = rx_error_count[0];
    assign LEDR[8:3] = 6'b0;
    assign LEDR[9]   = ~rst_n;

endmodule
