// debounce.v
// Cleans up a push button or slide switch.
//
//   1. Two flip-flops make the raw pin safe to use.
//   2. The output only changes after the input has held its new level for
//      STABLE_CLKS clocks in a row (default 10 ms), so contact bounce is
//      ignored.
//   3. rose / fell pulse for one clock when the clean level changes.
//
// After reset the module first waits STABLE_CLKS clocks and then simply
// takes over whatever level the pin has, without a rose / fell pulse. So a
// switch that is already up when the board starts does not count as a flip.

module debounce #(
    parameter integer STABLE_CLKS = 500_000
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
    reg        started;    // the starting level has been taken over

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sync    <= 2'b00;
            level   <= 1'b0;
            count   <= 32'd0;
            started <= 1'b0;
            rose    <= 1'b0;
            fell    <= 1'b0;
        end else begin
            sync <= {sync[0], raw};
            rose <= 1'b0;
            fell <= 1'b0;

            if (!started) begin
                if (count == STABLE_CLKS - 1) begin
                    count   <= 32'd0;
                    level   <= sync[1];
                    started <= 1'b1;
                end else begin
                    count <= count + 32'd1;
                end
            end else if (sync[1] == level) begin
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
