// reset_sync.v
// Turns the raw push-button reset into a clean reset for the 50 MHz domain.
//
//   - Assertion is asynchronous: pressing the button resets immediately,
//     even between clock edges.
//   - Release is synchronous: rst_n only goes high on a clock edge, two
//     clocks after the button is let go, so every flip-flop in the design
//     leaves reset on the same edge.
//
// MAX 10 registers power up at 0, so the design also starts in reset for
// two clocks right after the FPGA is programmed.

module reset_sync (
    input  wire clk,
    input  wire async_rst_n,   // raw active-low reset (KEY0, pressed = 0)
    output wire rst_n          // synchronised active-low reset
);

    reg [1:0] sync_ff = 2'b00;

    always @(posedge clk or negedge async_rst_n) begin
        if (!async_rst_n)
            sync_ff <= 2'b00;
        else
            sync_ff <= {sync_ff[0], 1'b1};
    end

    assign rst_n = sync_ff[1];

endmodule
