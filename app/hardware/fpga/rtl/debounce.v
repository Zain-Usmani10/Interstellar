// debounce.v
// Cleans up a push button or slide switch.
//
//   1. Two flip-flops make the raw pin safe to use.
//   2. The output only changes after the input has held its new level for
//      STABLE_CLKS clocks in a row (default 10 ms), so contact bounce is
//      ignored.
//   3. rose / fell pulse for one clock when the clean level changes.
//
// IDLE_LEVEL is the level at reset: 1 for the DE10-Lite keys (active low),
// 0 for a slide switch that starts down.

module debounce #(
    parameter integer STABLE_CLKS = 500_000,
    parameter         IDLE_LEVEL  = 1'b1
) (
    input  wire clk,
    input  wire rst_n,
    input  wire raw,       // straight from the pin
    output reg  level,     // debounced level
    output reg  rose,      // one-clock pulse: 0 -> 1
    output reg  fell       // one-clock pulse: 1 -> 0
);

    reg [1:0]  sync;
    reg [31:0] count;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sync  <= {2{IDLE_LEVEL}};
            level <= IDLE_LEVEL;
            count <= 32'd0;
            rose  <= 1'b0;
            fell  <= 1'b0;
        end else begin
            sync <= {sync[0], raw};
            rose <= 1'b0;
            fell <= 1'b0;

            if (sync[1] == level) begin
                count <= 32'd0;                 // no change pending
            end else if (count == STABLE_CLKS - 1) begin
                count <= 32'd0;
                level <= sync[1];
                rose  <= sync[1];
                fell  <= ~sync[1];
            end else begin
                count <= count + 32'd1;
            end
        end
    end

endmodule
