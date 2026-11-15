// bin2bcd.v
// Turns a binary number (0..999,999) into six decimal digits for the
// seven-segment displays.
//
// Method: "double dabble". The number is shifted in one bit at a time.
// Before each shift, any decimal digit that is 5 or more gets 3 added, which
// makes the shift carry correctly into the next digit.
//
// It runs all the time: every 21 clocks it takes the current value and
// updates the six output digits. That is far faster than the value changes.

module bin2bcd (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [19:0] value,      // must be <= 999,999
    output reg  [23:0] bcd         // six digits, digit 0 (ones) in bits [3:0]
);

    reg [19:0] shift;
    reg [23:0] work;
    reg [4:0]  bits_left;

    // Add 3 to every digit that is 5 or more.
    function [23:0] adjust;
        input [23:0] d;
        integer i;
        begin
            adjust = d;
            for (i = 0; i < 6; i = i + 1)
                if (d[i*4 +: 4] >= 4'd5)
                    adjust[i*4 +: 4] = d[i*4 +: 4] + 4'd3;
        end
    endfunction

    wire [23:0] adjusted = adjust(work);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            shift     <= 20'd0;
            work      <= 24'd0;
            bits_left <= 5'd0;
            bcd       <= 24'd0;
        end else if (bits_left == 5'd0) begin
            bcd       <= work;          // result of the conversion that just ended
            shift     <= value;         // start the next one
            work      <= 24'd0;
            bits_left <= 5'd20;
        end else begin
            work      <= {adjusted[22:0], shift[19]};
            shift     <= {shift[18:0], 1'b0};
            bits_left <= bits_left - 5'd1;
        end
    end

endmodule
