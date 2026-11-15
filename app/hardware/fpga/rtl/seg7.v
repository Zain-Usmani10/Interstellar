// seg7.v
// One seven-segment digit. Turns a symbol code into the seven segment
// signals of a DE10-Lite HEX display.
//
// Segment order in the output: bit 0 = a (top), 1 = b, 2 = c, 3 = d
// (bottom), 4 = e, 5 = f, 6 = g (middle). The displays are active low:
// 0 = segment on.
//
//      aaa
//     f   b
//      ggg
//     e   c
//      ddd
//
// Codes 0..9 are the digits. The rest are the symbols and letters the
// cockpit display needs.

module seg7 (
    input  wire [4:0] code,
    output wire [6:0] seg        // active low, {g,f,e,d,c,b,a}
);

    localparam [4:0] C_DASH  = 5'd10,
                     C_BLANK = 5'd11,
                     C_d     = 5'd12,
                     C_L     = 5'd13,
                     C_A     = 5'd14,
                     C_r     = 5'd15,
                     C_n     = 5'd16,
                     C_F     = 5'd17,
                     C_C     = 5'd18,
                     C_o     = 5'd19,
                     C_b     = 5'd20;

    reg [6:0] on;                // 1 = segment on, {g,f,e,d,c,b,a}

    always @(*) begin
        case (code)
            5'd0:    on = 7'b0111111;
            5'd1:    on = 7'b0000110;   // also used as the letter I
            5'd2:    on = 7'b1011011;
            5'd3:    on = 7'b1001111;
            5'd4:    on = 7'b1100110;
            5'd5:    on = 7'b1101101;   // also used as the letter S
            5'd6:    on = 7'b1111101;
            5'd7:    on = 7'b0000111;
            5'd8:    on = 7'b1111111;
            5'd9:    on = 7'b1101111;
            C_DASH:  on = 7'b1000000;
            C_BLANK: on = 7'b0000000;
            C_d:     on = 7'b1011110;
            C_L:     on = 7'b0111000;
            C_A:     on = 7'b1110111;
            C_r:     on = 7'b1010000;
            C_n:     on = 7'b1010100;
            C_F:     on = 7'b1110001;
            C_C:     on = 7'b0111001;
            C_o:     on = 7'b1011100;
            C_b:     on = 7'b1111100;
            default: on = 7'b0000000;
        endcase
    end

    assign seg = ~on;

endmodule
