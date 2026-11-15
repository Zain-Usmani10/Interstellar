// bringup_selftest.v
// BRING-UP HELPER. Lets the frame path be checked on the real board with
// one jumper wire (UART_TX to UART_RX) and no laptop bridge.
//
//   - Pressing KEY1 makes the board send itself a DISCOVER frame.
//   - With the jumper in, the board receives that DISCOVER, answers with a
//     STATUS frame, and then receives its own STATUS too. A STATUS is not a
//     command, so the receiver drops it and counts one error.
//   - good_led flips each time a good command frame is received.
//
// So with the jumper in, one KEY1 press = one good frame + one counted
// error. Without the jumper nothing is received and nothing changes.

module bringup_selftest (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         key_pressed,      // one-clock pulse from debounce
    input  wire         tx_free,          // frame_tx can take a frame now
    input  wire         frame_valid,      // a good command frame arrived
    // DISCOVER frame for frame_tx
    output reg          tx_start,
    output wire [7:0]   tx_type,
    output wire [15:0]  tx_seq,
    output wire [31:0]  tx_session,
    output wire [319:0] tx_payload,
    output wire [7:0]   tx_len,
    output reg          good_led
);

    assign tx_type    = 8'h01;      // DISCOVER
    assign tx_seq     = 16'd0;
    assign tx_session = 32'd0;
    assign tx_payload = 320'd0;
    assign tx_len     = 8'd0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_start <= 1'b0;
            good_led <= 1'b0;
        end else begin
            // A press while the transmitter is busy is simply ignored.
            tx_start <= key_pressed && tx_free && !tx_start;

            if (frame_valid)
                good_led <= ~good_led;
        end
    end

endmodule
