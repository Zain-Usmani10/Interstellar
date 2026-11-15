// uart_tx.v
// UART transmitter, 8 data bits, no parity, 1 stop bit (8N1), LSB first.
//
// How to use it:
//   - Wait until busy = 0.
//   - Put the byte on data and pulse start for one clock.
//   - busy stays 1 until the stop bit has finished.
// A start pulse while busy is ignored.
//
// The line idles high. Each bit lasts CLKS_PER_BIT clocks (434 = 115200 baud).

module uart_tx #(
    parameter integer CLKS_PER_BIT = 434
) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] data,
    input  wire       start,
    output reg        tx,       // pin, idles high
    output reg        busy
);

    // 10 bits on the wire: start (0), 8 data bits, stop (1).
    reg [9:0]  shift;
    reg [3:0]  bits_left;
    reg [15:0] clk_count;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx        <= 1'b1;
            busy      <= 1'b0;
            shift     <= 10'h3FF;
            bits_left <= 4'd0;
            clk_count <= 16'd0;
        end else if (!busy) begin
            tx <= 1'b1;
            if (start) begin
                shift     <= {1'b1, data, 1'b0};
                bits_left <= 4'd10;
                clk_count <= 16'd0;
                busy      <= 1'b1;
                tx        <= 1'b0;              // start bit begins now
            end
        end else begin
            if (clk_count == CLKS_PER_BIT - 1) begin
                clk_count <= 16'd0;
                if (bits_left == 4'd1) begin
                    busy <= 1'b0;               // stop bit finished
                    tx   <= 1'b1;
                end else begin
                    bits_left <= bits_left - 4'd1;
                    shift     <= {1'b1, shift[9:1]};
                    tx        <= shift[1];      // next bit
                end
            end else begin
                clk_count <= clk_count + 16'd1;
            end
        end
    end

endmodule
