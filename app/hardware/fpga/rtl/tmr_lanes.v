// tmr_lanes.v
// Three copies ("lanes") of the control tuple, A, B and C.
//
// Every clock all three are rewritten with the same next value, which the
// sequencer computes from the VOTED value. So a lane that got corrupted is
// repaired on the next clock.
//
// Fault injection for the demo: flip_a / flip_b are XORed into what lanes A
// and B store on this clock. A 1 bit flips that bit in the stored copy.
// Lane C is never touched.
//
// The preserve / dont_merge attributes stop Quartus from noticing that the
// three registers hold the same value and merging them into one. After a
// compile, check the map report: the lane registers must not appear under
// "Registers Removed During Synthesis".

module tmr_lanes #(
    parameter integer W           = 101,
    parameter [W-1:0] RESET_VALUE = {W{1'b0}}
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire [W-1:0] next,       // value to store in all three lanes
    input  wire [W-1:0] flip_a,     // bits to corrupt in lane A this clock
    input  wire [W-1:0] flip_b,     // bits to corrupt in lane B this clock
    output wire [W-1:0] lane_a,
    output wire [W-1:0] lane_b,
    output wire [W-1:0] lane_c
);

    (* preserve, dont_merge *) reg [W-1:0] reg_a;
    (* preserve, dont_merge *) reg [W-1:0] reg_b;
    (* preserve, dont_merge *) reg [W-1:0] reg_c;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reg_a <= RESET_VALUE;
            reg_b <= RESET_VALUE;
            reg_c <= RESET_VALUE;
        end else begin
            reg_a <= next ^ flip_a;
            reg_b <= next ^ flip_b;
            reg_c <= next;
        end
    end

    assign lane_a = reg_a;
    assign lane_b = reg_b;
    assign lane_c = reg_c;

endmodule
