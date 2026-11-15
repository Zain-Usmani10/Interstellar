// frame_tx.v
// Sends one protocol v1 frame through uart_tx, one byte at a time:
//   A5 5A | version=1 | type | sequence(2) | session(4) | length(2) | payload | CRC(2)
//
// How to use it:
//   - Wait until busy = 0.
//   - Set msg_type, seq, session, payload and payload_len, pulse start.
//   - All inputs are copied on that clock, so the frame is one consistent
//     snapshot even if the inputs change while it is being sent.
//
// payload is up to 40 bytes, byte 0 in bits [7:0] (sent first).

module frame_tx (
    input  wire         clk,
    input  wire         rst_n,
    // frame to send
    input  wire         start,
    input  wire [7:0]   msg_type,
    input  wire [15:0]  seq,
    input  wire [31:0]  session,
    input  wire [319:0] payload,
    input  wire [7:0]   payload_len,     // 0..40
    output reg          busy,
    // to uart_tx
    input  wire         tx_busy,
    output reg  [7:0]   tx_data,
    output reg          tx_start
);

    localparam [1:0] S_IDLE      = 2'd0,
                     S_PUT       = 2'd1,   // hand one byte to the UART
                     S_WAIT_BUSY = 2'd2,   // one clock for uart busy to rise
                     S_WAIT_DONE = 2'd3;   // wait until that byte is sent

    reg [1:0]   state;
    reg [7:0]   idx;             // which byte of the frame is next
    reg [7:0]   r_type;
    reg [15:0]  r_seq;
    reg [31:0]  r_session;
    reg [7:0]   r_len;
    reg [319:0] r_payload;       // shifts right one byte per payload byte sent
    reg [15:0]  crc;

    wire [8:0] payload_end = 9'd12 + {1'b0, r_len};   // index of the first CRC byte
    wire       in_payload  = (idx >= 8'd12) && ({1'b0, idx} < payload_end);
    wire       crc_covered = (idx >= 8'd2)  && ({1'b0, idx} < payload_end);
    wire       last_byte   = ({1'b0, idx} == payload_end + 9'd1);

    // Which byte goes out at position idx.
    reg [7:0] cur_byte;
    always @(*) begin
        case (idx)
            8'd0:  cur_byte = 8'hA5;
            8'd1:  cur_byte = 8'h5A;
            8'd2:  cur_byte = 8'h01;
            8'd3:  cur_byte = r_type;
            8'd4:  cur_byte = r_seq[7:0];
            8'd5:  cur_byte = r_seq[15:8];
            8'd6:  cur_byte = r_session[7:0];
            8'd7:  cur_byte = r_session[15:8];
            8'd8:  cur_byte = r_session[23:16];
            8'd9:  cur_byte = r_session[31:24];
            8'd10: cur_byte = r_len;
            8'd11: cur_byte = 8'h00;
            default: begin
                if (in_payload)                         cur_byte = r_payload[7:0];
                else if ({1'b0, idx} == payload_end)    cur_byte = crc[7:0];
                else                                    cur_byte = crc[15:8];
            end
        endcase
    end

    wire [15:0] crc_next;
    crc16 u_crc (
        .crc_in  (crc),
        .data    (cur_byte),
        .crc_out (crc_next)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state     <= S_IDLE;
            busy      <= 1'b0;
            idx       <= 8'd0;
            r_type    <= 8'd0;
            r_seq     <= 16'd0;
            r_session <= 32'd0;
            r_len     <= 8'd0;
            r_payload <= 320'd0;
            crc       <= 16'hFFFF;
            tx_data   <= 8'd0;
            tx_start  <= 1'b0;
        end else begin
            tx_start <= 1'b0;

            case (state)
                S_IDLE: begin
                    if (start) begin
                        r_type    <= msg_type;
                        r_seq     <= seq;
                        r_session <= session;
                        r_len     <= payload_len;
                        r_payload <= payload;
                        crc       <= 16'hFFFF;
                        idx       <= 8'd0;
                        busy      <= 1'b1;
                        state     <= S_PUT;
                    end
                end

                S_PUT: begin
                    tx_data  <= cur_byte;
                    tx_start <= 1'b1;
                    if (crc_covered) crc       <= crc_next;
                    if (in_payload)  r_payload <= {8'h00, r_payload[319:8]};
                    state <= S_WAIT_BUSY;
                end

                S_WAIT_BUSY: state <= S_WAIT_DONE;

                S_WAIT_DONE: begin
                    if (!tx_busy) begin
                        if (last_byte) begin
                            busy  <= 1'b0;
                            state <= S_IDLE;
                        end else begin
                            idx   <= idx + 8'd1;
                            state <= S_PUT;
                        end
                    end
                end
            endcase
        end
    end

endmodule
