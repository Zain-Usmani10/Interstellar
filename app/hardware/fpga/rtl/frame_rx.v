// frame_rx.v
// Turns the stream of received bytes into checked protocol v1 frames.
// It follows the reference parser in app/contracts/protocol_v1.py.
//
// Frame layout (all numbers little-endian):
//   A5 5A | version=1 | type | sequence(2) | session(4) | length(2) | payload | CRC(2)
//   The CRC covers version through the last payload byte.
//
// How it works:
//   - Every received byte is stored in a 256-byte ring buffer.
//   - A parser walks the buffer looking for A5 5A, then reads the frame.
//   - If the candidate turns out wrong (bad version, length over 128, bad
//     CRC, or it stays unfinished for 100 ms) the parser throws away ONE
//     byte and scans again from the next one. Because the bytes are still
//     in the buffer, a good frame hidden behind a broken one is not lost.
//   - A frame with a good CRC must also be a command this board accepts
//     with exactly the right payload length. Otherwise it is dropped.
//   - Every dropped candidate adds 1 to error_count. No reply is sent.
//
// Outputs: frame_valid pulses for one clock. frame_type, frame_seq,
// frame_session and frame_payload then hold that frame and stay unchanged
// until the next good frame.
//
// frame_payload holds up to 28 bytes, byte 0 in bits [7:0]. Little-endian
// fields can therefore be read directly, e.g. the first u32 is [31:0].

module frame_rx #(
    parameter integer TIMEOUT_CLKS = 5_000_000    // 100 ms at 50 MHz
) (
    input  wire         clk,
    input  wire         rst_n,
    // from uart_rx
    input  wire [7:0]   rx_data,
    input  wire         rx_valid,
    input  wire         rx_frame_error,
    // last good frame
    output reg          frame_valid,
    output reg  [7:0]   frame_type,
    output reg  [15:0]  frame_seq,
    output reg  [31:0]  frame_session,
    output reg  [223:0] frame_payload,
    // dropped frames, bad stop bits and buffer overflows
    output reg  [31:0]  error_count
);

    localparam [7:0] MAGIC0       = 8'hA5,
                     MAGIC1       = 8'h5A,
                     VERSION      = 8'h01;
    localparam integer MAX_PAYLOAD = 128;
    localparam integer HEADER_LEN  = 12;
    localparam integer STORE_BYTES = 28;          // longest payload we accept

    // ------------------------------------------------------------ ring buffer
    reg [7:0] mem [0:255];
    reg [7:0] wr_ptr;        // where the next received byte goes
    reg [7:0] cand_ptr;      // first byte of the frame candidate
    reg [7:0] rd_ptr;        // byte the parser looks at next
    reg [7:0] mem_q;         // byte read from the buffer
    reg       have_byte;     // mem_q is a real received byte

    wire buffer_full = (wr_ptr + 8'd1 == cand_ptr);

    // Memory has no reset so Quartus can use a RAM block.
    always @(posedge clk) begin
        if (rx_valid && !buffer_full)
            mem[wr_ptr] <= rx_data;
        mem_q <= mem[rd_ptr];
    end

    // ------------------------------------------------------------ parser state
    // The buffer read takes one clock, so the parser works in two phases:
    //   phase 0: wait for mem_q to load     phase 1: look at it and decide
    reg         phase;
    reg  [7:0]  idx;          // how many bytes of the candidate are consumed
    reg  [7:0]  len;          // payload length from the header
    reg  [7:0]  h_type;
    reg  [15:0] h_seq;
    reg  [31:0] h_session;
    reg  [223:0] h_payload;
    reg  [15:0] crc;
    reg         crc_lo_ok;
    reg  [31:0] timer;
    reg         parse_error;  // one-clock pulse

    wire [15:0] crc_next;
    crc16 u_crc (
        .crc_in  ((idx == 8'd2) ? 16'hFFFF : crc),
        .data    (mem_q),
        .crc_out (crc_next)
    );

    wire [8:0] payload_end = 9'd12 + {1'b0, len};       // index of the first CRC byte
    wire [7:0] pay_index   = idx - 8'd12;             // 0 for the first payload byte

    // Is this a command we accept, with exactly the right payload length?
    function shape_ok;
        input [7:0] t;
        input [7:0] l;
        begin
            case (t)
                8'h01, 8'h03:                      shape_ok = (l == 8'd0);   // DISCOVER, GET_STATUS
                8'h02, 8'h12, 8'h13, 8'h14, 8'h15: shape_ok = (l == 8'd4);   // OPEN_SESSION, ARM, START, ABORT, CLEAR
                8'h10:                             shape_ok = (l == 8'd28);  // LOAD_PLAN
                8'h11:                             shape_ok = (l == 8'd6);   // COMMIT_PLAN
                8'h16:                             shape_ok = (l == 8'd8);   // SET_TRIP_DAYS (proposed extension)
                default:                           shape_ok = 1'b0;
            endcase
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr        <= 8'd0;
            cand_ptr      <= 8'd0;
            rd_ptr        <= 8'd0;
            have_byte     <= 1'b0;
            phase         <= 1'b0;
            idx           <= 8'd0;
            len           <= 8'd0;
            h_type        <= 8'd0;
            h_seq         <= 16'd0;
            h_session     <= 32'd0;
            h_payload     <= 224'd0;
            crc           <= 16'hFFFF;
            crc_lo_ok     <= 1'b0;
            timer         <= 32'd0;
            parse_error   <= 1'b0;
            frame_valid   <= 1'b0;
            frame_type    <= 8'd0;
            frame_seq     <= 16'd0;
            frame_session <= 32'd0;
            frame_payload <= 224'd0;
            error_count   <= 32'd0;
        end else begin
            frame_valid <= 1'b0;
            parse_error <= 1'b0;

            // Store incoming bytes. A full buffer cannot happen in normal
            // use (the parser is thousands of times faster than the UART).
            if (rx_valid && !buffer_full)
                wr_ptr <= wr_ptr + 8'd1;

            error_count <= error_count
                         + {31'd0, parse_error}
                         + {31'd0, rx_frame_error}
                         + {31'd0, (rx_valid && buffer_full)};

            have_byte <= (rd_ptr != wr_ptr);
            phase     <= ~phase;

            // The 100 ms timer runs only while a candidate (A5 5A seen) is
            // waiting for more bytes.
            if (idx < 8'd2) timer <= 32'd0;
            else            timer <= timer + 32'd1;

            if (phase) begin
                if (idx >= 8'd2 && timer >= TIMEOUT_CLKS) begin
                    // Unfinished frame: give up on it.
                    parse_error <= 1'b1;
                    cand_ptr    <= cand_ptr + 8'd1;
                    rd_ptr      <= cand_ptr + 8'd1;
                    idx         <= 8'd0;
                end else if (have_byte) begin
                    // Default: accept this byte and move on.
                    rd_ptr <= rd_ptr + 8'd1;
                    idx    <= idx + 8'd1;

                    if (idx == 8'd0) begin
                        if (mem_q != MAGIC0) begin              // not a frame start: skip it
                            cand_ptr <= cand_ptr + 8'd1;
                            rd_ptr   <= cand_ptr + 8'd1;
                            idx      <= 8'd0;
                        end
                    end else if (idx == 8'd1) begin
                        if (mem_q != MAGIC1) begin              // A5 without 5A: skip the A5
                            cand_ptr <= cand_ptr + 8'd1;
                            rd_ptr   <= cand_ptr + 8'd1;
                            idx      <= 8'd0;
                        end
                    end else if (idx < HEADER_LEN) begin
                        crc <= crc_next;
                        case (idx)
                            8'd2: begin
                                h_payload <= 224'd0;
                                if (mem_q != VERSION) begin     // bad version
                                    parse_error <= 1'b1;
                                    cand_ptr    <= cand_ptr + 8'd1;
                                    rd_ptr      <= cand_ptr + 8'd1;
                                    idx         <= 8'd0;
                                end
                            end
                            8'd3:  h_type           <= mem_q;
                            8'd4:  h_seq[7:0]       <= mem_q;
                            8'd5:  h_seq[15:8]      <= mem_q;
                            8'd6:  h_session[7:0]   <= mem_q;
                            8'd7:  h_session[15:8]  <= mem_q;
                            8'd8:  h_session[23:16] <= mem_q;
                            8'd9:  h_session[31:24] <= mem_q;
                            8'd10: len              <= mem_q;
                            default: begin                      // 11: high byte of length
                                if (mem_q != 8'd0 || len > MAX_PAYLOAD) begin
                                    parse_error <= 1'b1;        // payload too long
                                    cand_ptr    <= cand_ptr + 8'd1;
                                    rd_ptr      <= cand_ptr + 8'd1;
                                    idx         <= 8'd0;
                                end
                            end
                        endcase
                    end else if ({1'b0, idx} < payload_end) begin
                        crc <= crc_next;
                        if (pay_index < STORE_BYTES)
                            h_payload[pay_index * 8 +: 8] <= mem_q;
                    end else if ({1'b0, idx} == payload_end) begin
                        crc_lo_ok <= (mem_q == crc[7:0]);       // CRC low byte first
                    end else begin
                        // Last byte of the frame: CRC high byte.
                        if (crc_lo_ok && mem_q == crc[15:8]) begin
                            // Good CRC: the whole frame is consumed.
                            cand_ptr <= rd_ptr + 8'd1;
                            idx      <= 8'd0;
                            if (shape_ok(h_type, len)) begin
                                frame_valid   <= 1'b1;
                                frame_type    <= h_type;
                                frame_seq     <= h_seq;
                                frame_session <= h_session;
                                frame_payload <= h_payload;
                            end else begin
                                parse_error <= 1'b1;            // unknown type or wrong length
                            end
                        end else begin
                            parse_error <= 1'b1;                // bad CRC
                            cand_ptr    <= cand_ptr + 8'd1;
                            rd_ptr      <= cand_ptr + 8'd1;
                            idx         <= 8'd0;
                        end
                    end
                end
            end
        end
    end

endmodule
