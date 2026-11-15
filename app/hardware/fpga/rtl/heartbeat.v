// heartbeat.v
// Blinks an LED so we can see the FPGA is configured and the clock runs.
// It counts 100 Hz ticks and flips the LED every HALF_PERIOD_TICKS ticks.
//
// Default: 50 ticks = 0.5 s on, 0.5 s off, so the LED blinks once a second.
// Because it is driven by the mission tick, a steady 1 Hz blink also shows
// that the 100 Hz tick itself is alive.

module heartbeat #(
    parameter integer HALF_PERIOD_TICKS = 50
) (
    input  wire clk,
    input  wire rst_n,
    input  wire tick,     // one-cycle 100 Hz enable from tick_gen
    output reg  led
);

    reg [15:0] count;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 16'd0;
            led   <= 1'b0;
        end else if (tick) begin
            if (count == HALF_PERIOD_TICKS - 1) begin
                count <= 16'd0;
                led   <= ~led;
            end else begin
                count <= count + 16'd1;
            end
        end
    end

endmodule
