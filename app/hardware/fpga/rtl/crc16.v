// crc16.v
// One step of CRC-16/CCITT-FALSE: polynomial 0x1021, bits taken MSB first.
// Feed it the CRC so far and one new byte; it returns the updated CRC.
// Pure logic, no clock. Start value is 0xFFFF (the user of this module
// supplies it). Check value: the bytes "123456789" give 0x29B1.

module crc16 (
    input  wire [15:0] crc_in,
    input  wire [7:0]  data,
    output wire [15:0] crc_out
);

    function [15:0] step;
        input [15:0] crc;
        input [7:0]  d;
        integer i;
        reg [15:0] c;
        begin
            c = crc ^ {d, 8'h00};
            for (i = 0; i < 8; i = i + 1) begin
                if (c[15])
                    c = {c[14:0], 1'b0} ^ 16'h1021;
                else
                    c = {c[14:0], 1'b0};
            end
            step = c;
        end
    endfunction

    assign crc_out = step(crc_in, data);

endmodule
