// tick_gen.v
// Clock-enable generator: tick is high for exactly one clk cycle out of
// every DIVISOR cycles. This is a pulse on the 50 MHz clock, not a new
// clock, so the whole design stays in one clock domain.
//
// Default: 50,000,000 / 500,000 = 100 Hz (the mission tick, spec section 4).
//
// restart = 1 sets the count back to zero, so the next tick comes exactly
// one full period later. The mission clock uses this on START.

module tick_gen #(
    parameter integer DIVISOR = 500_000
) (
    input  wire clk,
    input  wire rst_n,
    input  wire restart,
    output reg  tick
);

    // 32 bits is plenty: the largest divisor we use is 500,000.
    reg [31:0] count;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 32'd0;
            tick  <= 1'b0;
        end else if (restart) begin
            count <= 32'd0;
            tick  <= 1'b0;
        end else if (count == DIVISOR - 1) begin
            count <= 32'd0;
            tick  <= 1'b1;
        end else begin
            count <= count + 32'd1;
            tick  <= 1'b0;
        end
    end

endmodule
