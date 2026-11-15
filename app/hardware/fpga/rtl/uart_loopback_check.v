// uart_loopback_check.v
// TEMPORARY bring-up helper (milestone A). Removed when the frame layer
// takes over the UART in milestone B.
//
// Purpose: prove the UART pins work on the real board with one jumper wire
// from UART_TX to UART_RX, no laptop or bridge needed.
//
// What it does:
//   - Every 100 Hz tick it sends one byte (a counter that goes up by 1).
//   - Every byte that comes back is compared with the byte just sent.
//   - ok_led  : on while matching bytes keep arriving. It goes off about a
//               quarter of a second after they stop (jumper removed).
//   - err_led : turns on and stays on if a wrong byte or a bad stop bit is
//               ever seen. Cleared only by reset.

module uart_loopback_check #(
    parameter integer OK_HOLD_TICKS = 25     // 25 ticks at 100 Hz = 0.25 s
) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tick,            // 100 Hz enable
    // to uart_tx
    input  wire       tx_busy,
    output reg  [7:0] tx_data,
    output reg        tx_start,
    // from uart_rx
    input  wire [7:0] rx_data,
    input  wire       rx_valid,
    input  wire       rx_frame_error,
    // LEDs
    output wire       ok_led,
    output reg        err_led
);

    reg [7:0] ok_timer;

    assign ok_led = (ok_timer != 8'd0);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_data  <= 8'd0;
            tx_start <= 1'b0;
            ok_timer <= 8'd0;
            err_led  <= 1'b0;
        end else begin
            // Send the next counter value on every tick.
            tx_start <= 1'b0;
            if (tick && !tx_busy) begin
                tx_data  <= tx_data + 8'd1;
                tx_start <= 1'b1;
            end

            // Check what comes back. A byte takes under 0.1 ms on the wire,
            // so it always returns long before the next tick (10 ms).
            if (rx_valid && rx_data == tx_data)
                ok_timer <= OK_HOLD_TICKS[7:0];
            else if (tick && ok_timer != 8'd0)
                ok_timer <= ok_timer - 8'd1;

            if ((rx_valid && rx_data != tx_data) || rx_frame_error)
                err_led <= 1'b1;
        end
    end

endmodule
