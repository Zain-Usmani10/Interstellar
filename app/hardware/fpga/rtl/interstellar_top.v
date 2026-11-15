// interstellar_top.v
// Top level for the DE10-Lite (MAX 10 10M50DAF484C7G).
// This is the only file that connects modules to each other and to pins.
//
// Stage (issue #8, milestone D): the full command path with a triplicated,
// voted control tuple and fault-injection switches.
//
//   UART_RX -> uart_rx -> frame_rx -+-> cmd_handler -> sequencer
//                                   |        |             |
//                                   |       ACK         status
//                                   |        v             v
//   UART_TX <- uart_tx <- frame_tx <-------- + <------ status_gen
//
// Board controls:
//   KEY0   - reset (hold to reset, release to run)
//   KEY1   - local abort
//   SW0    - flip up: INJECT_SINGLE (corrupt one of the three copies)
//   SW1    - flip up: INJECT_DIVERGENCE (corrupt two copies differently)
//   LEDR0  - heartbeat, blinks once per second
//   LEDR1  - READY     (plan LOADED or ARMED)
//   LEDR2  - RUNNING
//   LEDR3  - COMPLETE
//   LEDR4  - SAFE
//   LEDR5  - ABORTED
//   LEDR6  - a fault was seen since reset (stays on)
//   LEDR7  - a session is open
//   LEDR8  - flips each time a received frame is dropped
//   LEDR9  - on while the design is held in reset
//   HEX5-4 - mission state as two letters; alternates with "nL" when the
//            link to the control station is lost
//   HEX3-0 - T-minus before the departure burn, then days to arrival

module interstellar_top #(
    // Overridden by testbenches so simulation runs fast. Never changed for
    // the real build.
    parameter integer TICK_DIVISOR         = 500_000,    // 50 MHz -> 100 Hz
    parameter integer HEARTBEAT_HALF_TICKS = 50,         // 100 Hz -> 1 Hz blink
    parameter integer UART_CLKS_PER_BIT    = 434,        // 50 MHz -> 115200 baud
    parameter integer FRAME_TIMEOUT_CLKS   = 5_000_000,  // 100 ms
    parameter integer STATUS_PERIOD_TICKS  = 10,         // 100 Hz -> 10 Hz STATUS
    parameter integer DEBOUNCE_CLKS        = 500_000,    // 10 ms
    parameter integer LINK_TIMEOUT_TICKS   = 200         // 2 s without a frame = link lost
) (
    input  wire       MAX10_CLK1_50,  // 50 MHz oscillator, PIN_P11
    input  wire [1:0] KEY,            // push buttons, active low
    input  wire [1:0] SW,             // slide switches, up = 1
    input  wire       UART_RX,        // JP1 pin 1, PIN_V10
    output wire       UART_TX,        // JP1 pin 2, PIN_W10
    output wire [9:0] LEDR,           // red LEDs, active high
    output wire [7:0] HEX0,           // seven-segment displays, active low,
    output wire [7:0] HEX1,           //   bit 7 = decimal point
    output wire [7:0] HEX2,
    output wire [7:0] HEX3,
    output wire [7:0] HEX4,
    output wire [7:0] HEX5,
    output wire [3:0] VGA_R,          // VGA monitor, 4 bits per colour
    output wire [3:0] VGA_G,
    output wire [3:0] VGA_B,
    output wire       VGA_HS,         // sync pulses, active low
    output wire       VGA_VS
);

    wire clk = MAX10_CLK1_50;
    wire rst_n;

    // ------------------------------------------------------------ reset and clocks
    reset_sync u_reset_sync (
        .clk         (clk),
        .async_rst_n (KEY[0]),
        .rst_n       (rst_n)
    );

    // Free-running 100 Hz: heartbeat and the 10 Hz STATUS period.
    wire tick_free;
    tick_gen #(
        .DIVISOR (TICK_DIVISOR)
    ) u_free_tick (
        .clk     (clk),
        .rst_n   (rst_n),
        .restart (1'b0),
        .tick    (tick_free)
    );

    // Mission 100 Hz: restarted by START so tick 1 is exactly 10 ms later.
    wire tick_mission;
    wire mission_tick_restart;
    tick_gen #(
        .DIVISOR (TICK_DIVISOR)
    ) u_mission_tick (
        .clk     (clk),
        .rst_n   (rst_n),
        .restart (mission_tick_restart),
        .tick    (tick_mission)
    );

    wire heartbeat_led;
    heartbeat #(
        .HALF_PERIOD_TICKS (HEARTBEAT_HALF_TICKS)
    ) u_heartbeat (
        .clk   (clk),
        .rst_n (rst_n),
        .tick  (tick_free),
        .led   (heartbeat_led)
    );

    // ------------------------------------------------------------ buttons and switches
    wire local_abort;         // KEY1 pressed (keys are active low: press = falling)
    wire inject_single;       // SW0 flipped up
    wire inject_divergence;   // SW1 flipped up

    debounce #(.STABLE_CLKS(DEBOUNCE_CLKS)) u_key1 (
        .clk(clk), .rst_n(rst_n), .raw(KEY[1]),
        .level(), .rose(), .fell(local_abort)
    );

    debounce #(.STABLE_CLKS(DEBOUNCE_CLKS)) u_sw0 (
        .clk(clk), .rst_n(rst_n), .raw(SW[0]),
        .level(), .rose(inject_single), .fell()
    );

    debounce #(.STABLE_CLKS(DEBOUNCE_CLKS)) u_sw1 (
        .clk(clk), .rst_n(rst_n), .raw(SW[1]),
        .level(), .rose(inject_divergence), .fell()
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

    // ------------------------------------------------------------ commands and mission
    wire        do_commit, do_arm, do_start, do_abort, do_clear;
    wire        do_set_days;
    wire [31:0] set_days_value;
    wire [31:0] staged_mission_id, staged_departure_tick, staged_arrival_tick, staged_end_tick;
    wire [31:0] staged_initial_fuel_g, staged_departure_fuel_g, staged_capture_fuel_g;
    wire [15:0] staged_crc16;
    wire [31:0] session;

    wire        plan_valid;
    wire [31:0] mission_id;
    wire [15:0] plan_crc16;
    wire [2:0]  state;
    wire [31:0] tick_count;
    wire [1:0]  executed_mask;
    wire [31:0] fuel_g;
    wire [31:0] departure_executed_tick;
    wire [31:0] capture_executed_tick;
    wire [2:0]  safe_reason;
    wire [31:0] masked_fault_count;
    wire [31:0] no_majority_count;
    wire        mission_changed;

    // Frame transmitter handshake (declared here, used below).
    wire         ftx_busy;
    wire         ack_start, st_start;
    wire [7:0]   ack_type,  st_type;
    wire [15:0]  ack_seq,   st_seq;
    wire [319:0] ack_payload, st_payload;
    wire [7:0]   ack_len,   st_len;
    wire         ack_pending, st_pending;

    // Free = idle and nobody started a frame on this clock.
    wire ftx_free = !ftx_busy && !ack_start && !st_start;

    cmd_handler u_cmd_handler (
        .clk                     (clk),
        .rst_n                   (rst_n),
        .frame_valid             (frame_valid),
        .frame_type              (frame_type),
        .frame_seq               (frame_seq),
        .frame_session           (frame_session),
        .frame_payload           (frame_payload),
        .state                   (state),
        .plan_valid              (plan_valid),
        .plan_mission_id         (mission_id),
        .plan_crc16              (plan_crc16),
        .tick_count              (tick_count),
        .do_commit               (do_commit),
        .do_arm                  (do_arm),
        .do_start                (do_start),
        .do_abort                (do_abort),
        .do_clear                (do_clear),
        .do_set_days             (do_set_days),
        .set_days_value          (set_days_value),
        .staged_mission_id       (staged_mission_id),
        .staged_departure_tick   (staged_departure_tick),
        .staged_arrival_tick     (staged_arrival_tick),
        .staged_end_tick         (staged_end_tick),
        .staged_initial_fuel_g   (staged_initial_fuel_g),
        .staged_departure_fuel_g (staged_departure_fuel_g),
        .staged_capture_fuel_g   (staged_capture_fuel_g),
        .staged_crc16            (staged_crc16),
        .session                 (session),
        .tx_free                 (ftx_free),
        .ack_start               (ack_start),
        .ack_type                (ack_type),
        .ack_seq                 (ack_seq),
        .ack_payload             (ack_payload),
        .ack_len                 (ack_len),
        .ack_pending             (ack_pending)
    );

    sequencer u_sequencer (
        .clk                     (clk),
        .rst_n                   (rst_n),
        .tick                    (tick_mission),
        .do_commit               (do_commit),
        .do_arm                  (do_arm),
        .do_start                (do_start),
        .do_abort                (do_abort),
        .do_clear                (do_clear),
        .local_abort             (local_abort),
        .inject_single           (inject_single),
        .inject_divergence       (inject_divergence),
        .staged_mission_id       (staged_mission_id),
        .staged_departure_tick   (staged_departure_tick),
        .staged_arrival_tick     (staged_arrival_tick),
        .staged_end_tick         (staged_end_tick),
        .staged_initial_fuel_g   (staged_initial_fuel_g),
        .staged_departure_fuel_g (staged_departure_fuel_g),
        .staged_capture_fuel_g   (staged_capture_fuel_g),
        .staged_crc16            (staged_crc16),
        .plan_valid              (plan_valid),
        .mission_id              (mission_id),
        .plan_crc16              (plan_crc16),
        .state                   (state),
        .tick_count              (tick_count),
        .executed_mask           (executed_mask),
        .fuel_g                  (fuel_g),
        .departure_executed_tick (departure_executed_tick),
        .capture_executed_tick   (capture_executed_tick),
        .safe_reason             (safe_reason),
        .masked_fault_count      (masked_fault_count),
        .no_majority_count       (no_majority_count),
        .tick_restart            (mission_tick_restart),
        .changed                 (mission_changed)
    );

    // ------------------------------------------------------------ STATUS
    // Sent when asked (DISCOVER 0x01, GET_STATUS 0x03), when the mission
    // changes, and 10 times a second.
    wire status_req = (frame_valid && (frame_type == 8'h01 || frame_type == 8'h03))
                    || mission_changed;

    status_gen #(
        .PERIOD_TICKS (STATUS_PERIOD_TICKS)
    ) u_status_gen (
        .clk                     (clk),
        .rst_n                   (rst_n),
        .send_req                (status_req),
        .period_tick             (tick_free),
        .tx_free                 (ftx_free && !ack_pending),   // ACKs go first
        .mission_id              (mission_id),
        .tick                    (tick_count),
        .state                   ({5'd0, state}),
        .executed_mask           ({6'd0, executed_mask}),
        .safe_reason             ({5'd0, safe_reason}),
        .fuel_remaining_g        (fuel_g),
        .departure_executed_tick (departure_executed_tick),
        .capture_executed_tick   (capture_executed_tick),
        .masked_fault_count      (masked_fault_count),
        .no_majority_count       (no_majority_count),
        .rx_error_count          (rx_error_count),
        .plan_crc16              (plan_crc16),
        .tx_start                (st_start),
        .tx_type                 (st_type),
        .tx_seq                  (st_seq),
        .tx_payload              (st_payload),
        .tx_len                  (st_len),
        .pending                 (st_pending)
    );

    // ------------------------------------------------------------ frames out
    // One transmitter, two senders. Only one of them starts at a time.
    frame_tx u_frame_tx (
        .clk         (clk),
        .rst_n       (rst_n),
        .start       (ack_start | st_start),
        .msg_type    (ack_start ? ack_type    : st_type),
        .seq         (ack_start ? ack_seq     : st_seq),
        .session     (session),
        .payload     (ack_start ? ack_payload : st_payload),
        .payload_len (ack_start ? ack_len     : st_len),
        .busy        (ftx_busy),
        .tx_busy     (tx_busy),
        .tx_data     (tx_data),
        .tx_start    (tx_start)
    );

    // ------------------------------------------------------------ cockpit (display only)
    // None of this feeds back into the mission.
    wire        link_seen;
    wire        link_lost;
    wire        trip_days_valid;
    wire [31:0] trip_days;
    wire [31:0] days_to_arrival;
    wire [31:0] plan_departure_tick;

    link_watchdog #(
        .TIMEOUT_TICKS (LINK_TIMEOUT_TICKS)
    ) u_link_watchdog (
        .clk         (clk),
        .rst_n       (rst_n),
        .tick        (tick_free),
        .frame_valid (frame_valid),
        .link_seen   (link_seen),
        .link_lost   (link_lost)
    );

    trip_clock u_trip_clock (
        .clk                   (clk),
        .rst_n                 (rst_n),
        .do_commit             (do_commit),
        .staged_departure_tick (staged_departure_tick),
        .staged_arrival_tick   (staged_arrival_tick),
        .do_start              (do_start),
        .do_clear              (do_clear),
        .do_set_days           (do_set_days),
        .set_days_value        (set_days_value),
        .tick_count            (tick_count),
        .trip_days_valid       (trip_days_valid),
        .trip_days             (trip_days),
        .days_to_arrival       (days_to_arrival),
        .departure_tick        (plan_departure_tick)
    );

    cockpit_display u_cockpit (
        .clk             (clk),
        .rst_n           (rst_n),
        .state           (state),
        .departed        (executed_mask[0]),
        .tick_count      (tick_count),
        .departure_tick  (plan_departure_tick),
        .trip_days_valid (trip_days_valid),
        .trip_days       (trip_days),
        .days_to_arrival (days_to_arrival),
        .link_lost       (link_lost),
        .blink           (heartbeat_led),
        .hex0            (HEX0),
        .hex1            (HEX1),
        .hex2            (HEX2),
        .hex3            (HEX3),
        .hex4            (HEX4),
        .hex5            (HEX5)
    );

    // ------------------------------------------------------------ VGA cockpit (display only)
    // The mission testbenches define SIM_NO_VGA (see run_sim.sh) to leave the
    // picture logic out and run faster; tb_vga.v tests it by itself. Quartus
    // never defines it, so the board always has the picture.
`ifndef SIM_NO_VGA
    vga_cockpit u_vga (
        .clk       (clk),
        .rst_n     (rst_n),
        .state     (state),
        .link_lost (link_lost),
        .blink     (heartbeat_led),
        .vga_r     (VGA_R),
        .vga_g     (VGA_G),
        .vga_b     (VGA_B),
        .vga_hs    (VGA_HS),
        .vga_vs    (VGA_VS)
    );
`else
    assign VGA_R  = 4'd0;
    assign VGA_G  = 4'd0;
    assign VGA_B  = 4'd0;
    assign VGA_HS = 1'b1;
    assign VGA_VS = 1'b1;
`endif

    // ------------------------------------------------------------ LEDs
    assign LEDR[0] = heartbeat_led;
    assign LEDR[1] = (state == 3'd1) || (state == 3'd2);   // READY
    assign LEDR[2] = (state == 3'd3);                       // RUNNING
    assign LEDR[3] = (state == 3'd5);                       // COMPLETE
    assign LEDR[4] = (state == 3'd4);                       // SAFE
    assign LEDR[5] = (state == 3'd6);                       // ABORTED
    assign LEDR[6] = (masked_fault_count != 32'd0) || (no_majority_count != 32'd0);
    assign LEDR[7] = (session != 32'd0);
    assign LEDR[8] = rx_error_count[0];
    assign LEDR[9] = ~rst_n;

endmodule
