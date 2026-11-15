// vga_bcd8.v
// Turns a binary number (0..99,999,999) into eight decimal digits, for the
// fuel readout on the VGA cockpit (fuel is in grams; the screen shows kg by
// dropping the last three digits).
//
// Same "double dabble" method as bin2bcd.v, just wider. It runs all the
// time: every 28 clocks it takes the current value and updates the digits.

module vga_bcd8 (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [26:0] value,      // must be <= 99,999,999
    output reg  [31:0] bcd         // eight digits, digit 0 (ones) in bits [3:0]
);

    reg [26:0] shift;
    reg [31:0] work;
    reg [4:0]  bits_left;

    // Add 3 to every digit that is 5 or more.
    function [31:0] adjust;
        input [31:0] d;
        integer i;
        begin
            adjust = d;
            for (i = 0; i < 8; i = i + 1)
                if (d[i*4 +: 4] >= 4'd5)
                    adjust[i*4 +: 4] = d[i*4 +: 4] + 4'd3;
        end
    endfunction

    wire [31:0] adjusted = adjust(work);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            shift     <= 27'd0;
            work      <= 32'd0;
            bits_left <= 5'd0;
            bcd       <= 32'd0;
        end else if (bits_left == 5'd0) begin
            bcd       <= work;          // result of the conversion that just ended
            shift     <= value;         // start the next one
            work      <= 32'd0;
            bits_left <= 5'd27;
        end else begin
            work      <= {adjusted[30:0], shift[26]};
            shift     <= {shift[25:0], 1'b0};
            bits_left <= bits_left - 5'd1;
        end
    end

endmodule
