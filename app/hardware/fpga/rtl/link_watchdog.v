// link_watchdog.v
// Tells the shuttle whether the control station is still talking to it.
//
//   - link_seen : at least one good command frame has arrived since reset.
//   - link_lost : a link was seen, and then no good frame arrived for
//                 TIMEOUT_TICKS ticks (default 200 = 2 seconds).
// Any good frame clears link_lost again.
//
// The control station must send something at least once a second (a
// GET_STATUS is enough) or the shuttle will report the link as lost.
//
// Display only. This flag never changes the mission: the shuttle flies the
// stored plan whether or not anyone is listening.

module link_watchdog #(
    parameter integer TIMEOUT_TICKS = 200
) (
    input  wire clk,
    input  wire rst_n,
    input  wire tick,          // free-running 100 Hz enable
    input  wire frame_valid,   // a good command frame arrived
    output reg  link_seen,
    output reg  link_lost
);

    reg [15:0] quiet_ticks;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            link_seen   <= 1'b0;
            link_lost   <= 1'b0;
            quiet_ticks <= 16'd0;
        end else if (frame_valid) begin
            link_seen   <= 1'b1;
            link_lost   <= 1'b0;
            quiet_ticks <= 16'd0;
        end else if (tick && link_seen && !link_lost) begin
            if (quiet_ticks == TIMEOUT_TICKS - 1)
                link_lost <= 1'b1;
            else
                quiet_ticks <= quiet_ticks + 16'd1;
        end
    end

endmodule
