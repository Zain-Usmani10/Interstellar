// vga_stars.v
// A field of stars that fly outward from the middle of the screen, which
// looks like flying forward through space.
//
// Each star keeps its position as an offset from the screen centre. Once
// per frame every star moves a small fraction further from the centre
// (offset = offset + offset / 2^k). Stars near the middle move slowly, stars
// near the edge move fast: the same thing perspective does. A star that
// leaves the screen is put back near the middle at a random place.
//
//   speed 0  stars stand still
//   speed 1  slow drift
//   speed 2  cruise
//   speed 3  fast: each star also draws two trailing dots (a streak)
//
// Display only.

module vga_stars #(
    parameter integer N = 48
) (
    input  wire               clk,
    input  wire               rst_n,
    input  wire               update,     // one pulse per frame, outside the picture
    input  wire [1:0]         speed,
    input  wire signed [10:0] px,         // this pixel's offset from the screen centre
    input  wire signed [10:0] py,
    output reg  [1:0]         level       // 0 nothing, 1 dim star, 2 bright star, 3 trail
);

    // Positions: 11 whole bits and 6 fraction bits, signed.
    reg [N*17-1:0] fx, fy;
    // Where the star was last frame, and the point halfway (for the trail).
    reg [N*11-1:0] ox, oy, mx, my;

    // ------------------------------------------------------------ random numbers
    reg [31:0] lfsr;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) lfsr <= 32'hC0FFEE01;
        else        lfsr <= {lfsr[30:0], lfsr[31] ^ lfsr[21] ^ lfsr[1] ^ lfsr[0]};
    end

    // ------------------------------------------------------------ move one star per clock
    reg        busy;
    reg        first;                     // first pass after reset: scatter everywhere
    reg [5:0]  idx;

    // Two clocks per star: first fetch its position, then work out the new one.
    reg               phase;
    reg signed [16:0] cur_x, cur_y;

    reg signed [16:0] step_x, step_y;
    always @(*) begin
        case (speed)
            2'd1:    begin step_x = cur_x >>> 6; step_y = cur_y >>> 6; end
            2'd2:    begin step_x = cur_x >>> 5; step_y = cur_y >>> 5; end
            2'd3:    begin step_x = cur_x >>> 3; step_y = cur_y >>> 3; end
            default: begin step_x = 17'sd0;      step_y = 17'sd0;      end
        endcase
    end

    wire signed [16:0] nxt_x = cur_x + step_x;
    wire signed [16:0] nxt_y = cur_y + step_y;
    wire signed [10:0] cur_xi = cur_x[16:6];
    wire signed [10:0] cur_yi = cur_y[16:6];
    wire signed [10:0] nxt_xi = nxt_x[16:6];
    wire signed [10:0] nxt_yi = nxt_y[16:6];

    wire gone = (nxt_xi > 11'sd318) || (nxt_xi < -11'sd319) ||
                (nxt_yi > 11'sd238) || (nxt_yi < -11'sd239) ||
                (cur_x == 17'sd0 && cur_y == 17'sd0);

    // A new random place: anywhere while standing still, near the middle while flying.
    wire               wide  = first || (speed == 2'd0);
    wire signed [10:0] new_x = wide ? ($signed({2'b00, lfsr[8:0]})   - 11'sd256)
                                    : ($signed({4'b0000, lfsr[6:0]}) - 11'sd64);
    wire signed [10:0] new_y = wide ? ($signed({2'b00, lfsr[19:11]})   - 11'sd256)
                                    : ($signed({4'b0000, lfsr[17:11]}) - 11'sd64);
    wire signed [11:0] mid_x = cur_xi + nxt_xi;
    wire signed [11:0] mid_y = cur_yi + nxt_yi;

    // The pass counter: walks through the stars once per frame.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy  <= 1'b0;
            first <= 1'b1;
            idx   <= 6'd0;
            phase <= 1'b0;
            cur_x <= 17'sd0;
            cur_y <= 17'sd0;
        end else if (update && !busy) begin
            busy  <= 1'b1;
            idx   <= 6'd0;
            phase <= 1'b0;
        end else if (busy && !phase) begin
            cur_x <= fx[idx*17 +: 17];
            cur_y <= fy[idx*17 +: 17];
            phase <= 1'b1;
        end else if (busy) begin
            phase <= 1'b0;
            if (idx == N - 1) begin
                busy  <= 1'b0;
                first <= 1'b0;
            end else begin
                idx <= idx + 6'd1;
            end
        end
    end

    // One set of registers per star; star number idx is updated this clock.
    // The same block says whether this pixel is on that star.
    wire [N-1:0] hit_dim, hit_bright, hit_tail;

    genvar g;
    generate
        for (g = 0; g < N; g = g + 1) begin : star
            wire signed [10:0] sx = fx[g*17 + 6 +: 11];
            wire signed [10:0] sy = fy[g*17 + 6 +: 11];

            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    fx[g*17 +: 17] <= 17'd0;   fy[g*17 +: 17] <= 17'd0;
                    ox[g*11 +: 11] <= 11'd0;   oy[g*11 +: 11] <= 11'd0;
                    mx[g*11 +: 11] <= 11'd0;   my[g*11 +: 11] <= 11'd0;
                end else if (busy && phase && idx == g) begin
                    if (gone || first) begin
                        fx[g*17 +: 17] <= {new_x, 6'd0};
                        fy[g*17 +: 17] <= {new_y, 6'd0};
                        ox[g*11 +: 11] <= new_x;   oy[g*11 +: 11] <= new_y;
                        mx[g*11 +: 11] <= new_x;   my[g*11 +: 11] <= new_y;
                    end else begin
                        fx[g*17 +: 17] <= nxt_x;
                        fy[g*17 +: 17] <= nxt_y;
                        ox[g*11 +: 11] <= cur_xi;  oy[g*11 +: 11] <= cur_yi;
                        mx[g*11 +: 11] <= mid_x[11:1];
                        my[g*11 +: 11] <= mid_y[11:1];
                    end
                end
            end

            // Stars far from the middle are "closer": drawn 2 x 2 and bright.
            wire far = (sx > 11'sd96) || (sx < -11'sd96) || (sy > 11'sd96) || (sy < -11'sd96);
            wire on  = far ? ((px[10:1] == sx[10:1]) && (py[10:1] == sy[10:1]))
                           : ((px == sx) && (py == sy));
            assign hit_bright[g] = on && far;
            assign hit_dim[g]    = on && !far;
            // The trail: 2 x 2 dots at last frame's place and halfway.
            assign hit_tail[g]   = (speed == 2'd3) &&
                (((px[10:1] == mx[g*11 + 1 +: 10]) && (py[10:1] == my[g*11 + 1 +: 10])) ||
                 ((px[10:1] == ox[g*11 + 1 +: 10]) && (py[10:1] == oy[g*11 + 1 +: 10])));
        end
    endgenerate

    always @(*) begin
        if (|hit_bright)    level = 2'd2;
        else if (|hit_dim)  level = 2'd1;
        else if (|hit_tail) level = 2'd3;
        else                level = 2'd0;
    end

endmodule
