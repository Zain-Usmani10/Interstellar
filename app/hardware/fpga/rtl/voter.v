// voter.v
// Majority vote over three copies of the control tuple.
//
// The WHOLE tuple is compared, not bit by bit:
//   - If any two copies are equal, that value wins.
//   - If all three are different there is no majority.
// Voting bit by bit could build a value that none of the copies ever held.
//
// Pure logic, no clock.

module voter #(
    parameter integer W = 101
) (
    input  wire [W-1:0] a,
    input  wire [W-1:0] b,
    input  wire [W-1:0] c,
    output wire [W-1:0] voted,        // majority value (meaningless if !majority_ok)
    output wire         majority_ok,  // at least two copies agree
    output wire         mismatch      // at least one copy differs
);

    wire ab = (a == b);
    wire ac = (a == c);
    wire bc = (b == c);

    assign majority_ok = ab | ac | bc;
    assign mismatch    = !(ab & ac);
    assign voted       = (ab | ac) ? a : b;   // a is in the majority, else b == c

endmodule
