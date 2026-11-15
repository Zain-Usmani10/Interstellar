// uart_rx.v
// UART receiver, 8 data bits, no parity, 1 stop bit (8N1), LSB first.
//
// How it works:
//   1. The RX pin goes through two flip-flops so it is safe to use.
//   2. The line idles high. A low level is a possible start bit.
//   3. Half a bit later we look again. Still low = real start bit.
//      (A short glitch is ignored.)
//   4. We then sample once per bit time, which lands in the middle of each
//      of the 8 data bits, then the stop bit.
//   5. Stop bit high -> valid pulses for one clock with the byte on data.
//      Stop bit low  -> frame_error pulses instead and the byte is dropped.
//
// CLKS_PER_BIT = 50,000,000 / 115,200 = 434.

module uart_rx #(
    parameter integer CLKS_PER_BIT = 434
) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       rx,           // raw pin, idles high
    output reg  [7:0] data,         // received byte, good when valid = 1
    output reg        valid,        // one-clock pulse: a byte arrived
    output reg        frame_error   // one-clock pulse: bad stop bit
);

    localparam [2:0] S_IDLE      = 3'd0,
                     S_START     = 3'd1,
                     S_DATA      = 3'd2,
                     S_STOP      = 3'd3,
                     S_WAIT_HIGH = 3'd4;   // after an error, wait for idle

    // Two-flop synchroniser. Resets to 1 because the line idles high.
    reg [1:0] rx_sync;
    wire      rx_s = rx_sync[1];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) rx_sync <= 2'b11;
        else        rx_sync <= {rx_sync[0], rx};
    end

    reg [2:0]  state;
    reg [15:0] clk_count;
    reg [2:0]  bit_index;
    reg [7:0]  shift;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state       <= S_IDLE;
            clk_count   <= 16'd0;
            bit_index   <= 3'd0;
            shift       <= 8'd0;
            data        <= 8'd0;
            valid       <= 1'b0;
            frame_error <= 1'b0;
        end else begin
            valid       <= 1'b0;
            frame_error <= 1'b0;

            case (state)
                S_IDLE: begin
                    clk_count <= 16'd0;
                    if (!rx_s)
                        state <= S_START;
                end

                // Wait to the middle of the start bit and check it again.
                S_START: begin
                    if (clk_count == (CLKS_PER_BIT / 2) - 1) begin
                        clk_count <= 16'd0;
                        bit_index <= 3'd0;
                        state     <= rx_s ? S_IDLE : S_DATA;
                    end else begin
                        clk_count <= clk_count + 16'd1;
                    end
                end

                // One full bit time later we are in the middle of a data bit.
                S_DATA: begin
                    if (clk_count == CLKS_PER_BIT - 1) begin
                        clk_count <= 16'd0;
                        shift     <= {rx_s, shift[7:1]};   // LSB arrives first
                        if (bit_index == 3'd7)
                            state <= S_STOP;
                        else
                            bit_index <= bit_index + 3'd1;
                    end else begin
                        clk_count <= clk_count + 16'd1;
                    end
                end

                S_STOP: begin
                    if (clk_count == CLKS_PER_BIT - 1) begin
                        clk_count <= 16'd0;
                        if (rx_s) begin
                            data  <= shift;
                            valid <= 1'b1;
                            state <= S_IDLE;
                        end else begin
                            frame_error <= 1'b1;
                            state       <= S_WAIT_HIGH;
                        end
                    end else begin
                        clk_count <= clk_count + 16'd1;
                    end
                end

                // Do not treat a stuck-low line as a stream of start bits.
                S_WAIT_HIGH: begin
                    if (rx_s)
                        state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
