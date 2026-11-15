// vga_cockpit.v
// The shuttle's cockpit picture on the VGA monitor: the pilot's view through
// the windshield, with a dashboard underneath. 640 x 480, 4 bits per colour.
//
// STEP 2 (this version): a SAMPLE REEL. Eight scenes, six seconds each, in a
// loop, so the team can pick the look. Each scene has a big letter:
//   A docked   B countdown   C liftoff   D cruise
//   E fast cruise   F arrival   G link lost   H safe mode
// The numbers in the reel are SAMPLES, not board values, and the screen says
// "SAMPLE REEL". The only live board values are the two lamps at the top
// right (mission state colour, link). The next step replaces the reel timer
// with the real mission state and the real numbers.
//
// Nothing is stored as pictures. Every pixel is worked out as it is drawn:
//   stars   vga_stars.v (points that fly outward from the centre)
//   planet  one circle test, (dx*dx + dy*dy) < r*r, with bands and a shadow
//   cockpit rectangles and two slanted struts
//   words   vga_font.v + vga_reel_text.v
//
// Two steps per pixel: step 1 does the heavy sums and stores the results,
// step 2 picks the colour. Display only: nothing here feeds the mission.

module vga_cockpit #(
    parameter integer SCENE_FRAMES = 360,         // 6 s at 60 frames per second
    parameter integer STARS        = 48
) (
    input  wire       clk,
    input  wire       rst_n,

    // live board values
    input  wire [2:0] state,
    input  wire       link_lost,
    input  wire       blink,                      // 1 Hz square wave

    output reg  [3:0] vga_r,
    output reg  [3:0] vga_g,
    output reg  [3:0] vga_b,
    output reg        vga_hs,
    output reg        vga_vs
);

    localparam [2:0] SC_DOCKED = 3'd0, SC_COUNT = 3'd1, SC_LIFTOFF = 3'd2, SC_CRUISE = 3'd3,
                     SC_FAST   = 3'd4, SC_ARRIVAL = 3'd5, SC_NOLINK = 3'd6, SC_SAFE   = 3'd7;

    // ------------------------------------------------------------ timing
    wire       pix_en;
    wire [9:0] x, y;
    wire       active, hsync, vsync, frame_start;

    vga_sync u_sync (
        .clk(clk), .rst_n(rst_n), .pix_en(pix_en), .x(x), .y(y),
        .active(active), .hsync(hsync), .vsync(vsync), .frame_start(frame_start)
    );

    // One pulse per frame, just below the picture: the moment to move things.
    wire frame_tick = pix_en && (x == 10'd0) && (y == 10'd480);

    // ------------------------------------------------------------ the reel: which scene, how far into it
    reg [2:0]  scene;
    reg [8:0]  t;                 // frames since the scene began
    reg [7:0]  slow;              // counts every 4th frame, for dashboard lights
    reg [1:0]  slow_div;
    reg [15:0] frame_rand;        // a new random number every frame
    reg [3:0]  days2, days1, days0;   // sample days counter (decimal digits)
    reg [2:0]  days_div;
    reg [2:0]  count_s;           // sample countdown seconds
    reg [5:0]  count_div;

    wire scene_end = (t == SCENE_FRAMES - 1);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            scene <= 3'd0;  t <= 9'd0;  slow <= 8'd0;  slow_div <= 2'd0;
            frame_rand <= 16'hACE1;
            days2 <= 4'd1;  days1 <= 4'd1;  days0 <= 4'd1;  days_div <= 3'd0;
            count_s <= 3'd5;  count_div <= 6'd0;
        end else if (frame_tick) begin
            frame_rand <= {frame_rand[14:0], frame_rand[15] ^ frame_rand[13] ^ frame_rand[12] ^ frame_rand[10]};
            slow_div   <= slow_div + 2'd1;
            if (slow_div == 2'd3) slow <= slow + 8'd1;

            if (scene_end) begin
                t         <= 9'd0;
                scene     <= scene + 3'd1;
                days2     <= 4'd1;  days1 <= 4'd1;  days0 <= 4'd1;  days_div <= 3'd0;
                count_s   <= 3'd5;  count_div <= 6'd0;
            end else begin
                t <= t + 9'd1;

                days_div <= days_div + 3'd1;                 // one sample "day" every 8 frames
                if (days_div == 3'd7 && {days2, days1, days0} != 12'h000) begin
                    if (days0 != 4'd0) days0 <= days0 - 4'd1;
                    else begin
                        days0 <= 4'd9;
                        if (days1 != 4'd0) days1 <= days1 - 4'd1;
                        else begin days1 <= 4'd9; days2 <= days2 - 4'd1; end
                    end
                end

                count_div <= count_div + 6'd1;               // countdown: one second = 60 frames
                if (count_div == 6'd59) begin
                    count_div <= 6'd0;
                    if (count_s != 3'd0) count_s <= count_s - 3'd1;
                end
            end
        end
    end

    // ------------------------------------------------------------ per-scene settings
    // Launch shake: a random 0..3 pixel jolt for the first three seconds.
    wire [9:0] rise  = (scene == SC_LIFTOFF) ? ({1'b0, t} >> 1) : 10'd0;
    wire [9:0] shake = (scene == SC_LIFTOFF && t < 9'd180) ? {8'd0, frame_rand[1:0]} : 10'd0;
    wire [9:0] drop  = rise + shake;          // how far the ground has fallen away

    reg  [1:0]         star_speed;
    reg  signed [11:0] ccx, ccy;              // circle centre (screen pixels)
    reg  [9:0]         cr;                    // circle radius, 0 = no circle
    reg                ground;                // the circle is the planet we sit on

    always @(*) begin
        star_speed = 2'd0;
        ccx = 12'sd320;  ccy = 12'sd210;  cr = 10'd0;  ground = 1'b0;
        case (scene)
            SC_DOCKED, SC_COUNT: begin
                ccy = 12'sd1150;  cr = 10'd900;  ground = 1'b1;
            end
            SC_LIFTOFF: begin
                ccy = 12'sd1150 + $signed({2'b00, drop});  cr = 10'd900;  ground = 1'b1;
                star_speed = (t < 9'd150) ? 2'd0 : 2'd1;
            end
            SC_CRUISE, SC_NOLINK: begin
                star_speed = 2'd2;
                ccx = 12'sd430;  ccy = 12'sd170;  cr = 10'd10;       // far-off destination
            end
            SC_FAST: begin
                star_speed = 2'd3;
            end
            SC_ARRIVAL: begin
                star_speed = 2'd1;
                cr = 10'd20 + {2'b00, t[8:1]};                          // grows as we approach
            end
            default: begin                                               // SC_SAFE
                cr = 10'd120;
            end
        endcase
    end

    // ------------------------------------------------------------ step 1: the heavy sums
    wire signed [10:0] px = $signed({1'b0, x}) - 11'sd320;     // offset from screen centre
    wire signed [10:0] py = $signed({1'b0, y}) - 11'sd240;

    // Stars.
    wire [1:0] star_level;
    vga_stars #(.N(STARS)) u_stars (
        .clk(clk), .rst_n(rst_n), .update(frame_tick), .speed(star_speed),
        .px(px), .py(py), .level(star_level)
    );

    // The circle (planet).
    wire signed [11:0] dx = $signed({2'b00, x}) - ccx;
    wire signed [11:0] dy = $signed({2'b00, y}) - ccy;
    wire [23:0] d2      = dx * dx + dy * dy;
    wire [10:0] cr_rim  = {1'b0, cr} + 11'd5;
    wire [23:0] r2      = cr * cr;
    wire [23:0] r2_rim  = cr_rim * cr_rim;
    wire        in_body = (cr != 10'd0) && (d2 < r2);
    wire        in_rim  = (cr != 10'd0) && (d2 >= r2) && (d2 < r2_rim);     // thin glow of air
    wire [23:0] depth   = r2 - d2;                                           // how far inside
    // Night side: light comes from the upper left.
    wire signed [12:0] dsum   = dx + dy;
    wire               shadow = dsum > $signed({4'b0000, cr[9:1]});
    // Cloud bands that scale with the planet: compare 4*dy with multiples of r.
    wire signed [14:0] dy4 = {dy, 2'b00};
    wire signed [14:0] r1  = $signed({5'b00000, cr});
    wire signed [14:0] r2x = r1 <<< 1;
    wire signed [14:0] r3x = r2x + r1;
    wire band    = (dy4 > -r3x) ^ (dy4 > -r2x) ^ (dy4 > -r1) ^ (dy4 > 15'sd0) ^
                   (dy4 > r1)   ^ (dy4 > r2x)  ^ (dy4 > r3x);
    wire equator = (dy4 > -r1) && (dy4 < r1);
    // Sparse lights on the ground: a cheap scramble of the 4 x 4 pixel cell number.
    wire [7:0] cell_mix = dx[9:2] ^ {dy[6:2], dy[9:7]} ^ {dx[4:2], dx[9:5]};
    wire       city     = (cell_mix[5:0] == 6'd17);

    // Words: the small text grid and the one big scene letter.
    wire       txt_cell_on;
    wire [5:0] txt_code_raw;
    vga_reel_text u_text (
        .scene(scene), .row(y[8:4]), .col(x[9:4]), .on(txt_cell_on), .code(txt_code_raw)
    );

    reg [5:0] txt_code;                       // fill in the live digits
    always @(*) begin
        case (txt_code_raw)
            6'd60:   txt_code = {2'b00, days2};
            6'd61:   txt_code = {2'b00, days1};
            6'd62:   txt_code = {2'b00, days0};
            6'd63:   txt_code = {3'b000, count_s};
            default: txt_code = txt_code_raw;
        endcase
    end

    wire [4:0] txt_bits;
    vga_font u_font_small (.code(txt_code), .row(y[3:1]), .bits(txt_bits));
    // Each cell is 8 x 8 font pixels (doubled on screen); the letter uses columns 1..5, rows 0..6.
    wire [2:0] fcx     = x[3:1];
    wire       txt_pix = txt_cell_on && (y[3:1] != 3'd7) && (fcx >= 3'd1) && (fcx <= 3'd5) &&
                         txt_bits[3'd5 - fcx];

    wire [9:0] bx      = x - 10'd112;         // big letter: 8 x scale at (112, 280)
    wire [9:0] by      = y - 10'd280;
    wire       big_box = (x >= 10'd112) && (x < 10'd152) && (y >= 10'd280) && (y < 10'd336);
    wire [4:0] big_bits;
    vga_font u_font_big (.code({3'b000, scene} + 6'd10), .row(by[5:3]), .bits(big_bits));
    wire       big_pix = big_box && big_bits[3'd4 - bx[5:3]];

    // Store the results, and the pixel position they belong to.
    reg [9:0]  x1, y1;
    reg        act1, hs1, vs1;
    reg [1:0]  star1;
    reg        body1, rim1, shadow1, band1, equator1, city1, stripe1, txt1, big1;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            x1 <= 10'd0;  y1 <= 10'd0;  act1 <= 1'b0;  hs1 <= 1'b1;  vs1 <= 1'b1;
            star1 <= 2'd0;
            {body1, rim1, shadow1, band1, equator1, city1, stripe1, txt1, big1} <= 9'd0;
        end else if (pix_en) begin
            x1 <= x;  y1 <= y;  act1 <= active;  hs1 <= hsync;  vs1 <= vsync;
            star1    <= star_level;
            body1    <= in_body;
            rim1     <= in_rim;
            shadow1  <= shadow;
            band1    <= band;
            equator1 <= equator;
            city1    <= city;
            stripe1  <= depth[15];
            txt1     <= txt_pix;
            big1     <= big_pix;
        end
    end

    // ------------------------------------------------------------ step 2: pick the colour
    // -- the cockpit frame
    wire [9:0] strut_l = 10'd150 - {2'b00, y1[9:2]};          // slanted struts
    wire [9:0] strut_r = 10'd490 + {2'b00, y1[9:2]};
    wire in_strut_l = (x1 + 10'd10 >= strut_l) && (x1 < strut_l + 10'd10);
    wire in_strut_r = (x1 + 10'd10 >= strut_r) && (x1 < strut_r + 10'd10);
    wire strut_edge = (x1 + 10'd10 == strut_l) || (x1 + 10'd9 == strut_l) ||
                      (x1 == strut_r + 10'd9)  || (x1 == strut_r + 10'd8) ||
                      (x1 + 10'd1 == strut_l + 10'd10) || (x1 + 10'd10 == strut_r);
    wire top_bar = (y1 < 10'd40);
    wire dash    = (y1 >= 10'd360);
    wire glass   = !top_bar && !dash && !in_strut_l && !in_strut_r;

    // -- dashboard screens
    wire scr_c   = (x1 >= 10'd200) && (x1 < 10'd440) && (y1 >= 10'd376) && (y1 < 10'd456);
    wire scr_l   = (x1 >= 10'd40)  && (x1 < 10'd184) && (y1 >= 10'd376) && (y1 < 10'd456);
    wire scr_r   = (x1 >= 10'd456) && (x1 < 10'd600) && (y1 >= 10'd376) && (y1 < 10'd456);
    wire scr_c_edge = scr_c && (x1 == 10'd200 || x1 == 10'd439 || y1 == 10'd376 || y1 == 10'd455);
    wire scr_l_edge = scr_l && (x1 == 10'd40  || x1 == 10'd183 || y1 == 10'd376 || y1 == 10'd455);
    wire scr_r_edge = scr_r && (x1 == 10'd456 || x1 == 10'd599 || y1 == 10'd376 || y1 == 10'd455);

    // left screen: eight bars that rise and fall
    wire [2:0] bar_k   = x1[6:4] - 3'd3;                       // bars in text columns 3..10
    wire [5:0] bar_h   = slow[5:0] + {bar_k, 3'b000} + {3'b000, bar_k};
    wire [5:0] bar_tri = bar_h[5] ? ~bar_h : bar_h;            // up then down
    wire [9:0] bar_top = 10'd448 - {4'd0, bar_tri[4:0], 1'b0};
    wire       bar_on  = scr_l && (x1 >= 10'd48) && (x1 < 10'd176) &&
                         (x1[3:0] >= 4'd2) && (x1[3:0] <= 4'd13) && (y1 >= bar_top) && (y1 < 10'd448);
    wire       bar_cap = bar_on && (y1 < bar_top + 10'd3);

    // right screen: a grid of status lights that change now and then
    wire [5:0] lamp_mix = {x1[6:4], y1[6:4]} ^ slow[7:2] ^ {y1[6:4], x1[6:4]} + {3'b000, x1[6:4]};
    wire       lamp_in  = scr_r && (x1 >= 10'd464) && (x1 < 10'd592) && (y1 >= 10'd384) && (y1 < 10'd448) &&
                          (x1[3:0] >= 4'd3) && (x1[3:0] <= 4'd12) && (y1[3:0] >= 4'd3) && (y1[3:0] <= 4'd12);
    wire       lamp_lit = lamp_in && (lamp_mix[1:0] != 2'd0);

    // top bar: two LIVE lamps (mission state colour, link) at the right
    wire lamp_state = (y1 >= 10'd12) && (y1 < 10'd28) && (x1 >= 10'd592) && (x1 < 10'd608);
    wire lamp_link  = (y1 >= 10'd12) && (y1 < 10'd28) && (x1 >= 10'd616) && (x1 < 10'd632);

    reg [11:0] state_colour;
    always @(*) begin
        case (state)
            3'd0:    state_colour = 12'h888;    // IDLE      grey
            3'd1:    state_colour = 12'h24F;    // LOADED    blue
            3'd2:    state_colour = 12'h24F;    // ARMED     blue
            3'd3:    state_colour = 12'h0F0;    // RUNNING   green
            3'd4:    state_colour = 12'hFA0;    // SAFE      amber
            3'd5:    state_colour = 12'hFFF;    // COMPLETE  white
            3'd6:    state_colour = 12'hF00;    // ABORTED   red
            default: state_colour = 12'h000;
        endcase
    end

    // -- things seen through the glass
    wire [9:0] gy = y1 - drop;                                  // launch tower moves with the ground
    wire tower_scene = (scene == SC_DOCKED) || (scene == SC_COUNT) || (scene == SC_LIFTOFF);
    wire tower   = tower_scene && (x1 >= 10'd392) && (x1 < 10'd424) && (y1 >= 10'd130 + drop);
    wire tower_bar = (x1[2:0] == 3'd0) || (gy[2:0] == 3'd0) || (x1[4:0] == gy[4:0]);
    wire arm     = tower_scene && (x1 >= 10'd336) && (x1 < 10'd392) &&
                   (y1 >= 10'd150 + drop) && (y1 < 10'd158 + drop);
    wire beacon  = tower_scene && (x1 >= 10'd404) && (x1 < 10'd412) &&
                   (y1 >= 10'd120 + drop) && (y1 < 10'd130 + drop) && t[4];

    wire reticle_scene = (scene == SC_CRUISE) || (scene == SC_FAST) || (scene == SC_ARRIVAL) || (scene == SC_NOLINK);
    wire [9:0] adx = (x1 >= 10'd320) ? (x1 - 10'd320) : (10'd320 - x1);
    wire [9:0] ady = (y1 >= 10'd200) ? (y1 - 10'd200) : (10'd200 - y1);
    wire reticle = reticle_scene &&
                   (((y1 == 10'd200) && (adx >= 10'd14) && (adx < 10'd44)) ||
                    ((x1 == 10'd320) && (ady >= 10'd14) && (ady < 10'd44)) ||
                    ((adx == 10'd80) && (ady >= 10'd60) && (ady <= 10'd80)) ||      // corner brackets
                    ((ady == 10'd80) && (adx >= 10'd60) && (adx <= 10'd80)));

    wire banner_scene = (scene == SC_NOLINK) || (scene == SC_SAFE);
    wire banner  = banner_scene && (x1 >= 10'd128) && (x1 < 10'd512) && (y1 >= 10'd72) && (y1 < 10'd104);
    wire alert_edge = (scene == SC_SAFE) && t[4] &&
                      ((y1 >= 10'd42 && y1 < 10'd48) || (y1 >= 10'd352 && y1 < 10'd358));

    // engine glow from below the windshield
    wire glow_on = ((scene == SC_COUNT) && (count_s <= 3'd2)) || ((scene == SC_LIFTOFF) && (t < 9'd240));
    wire [9:0] glow_d = y1 - 10'd280;
    wire [3:0] glow_raw = (y1 >= 10'd280) ? glow_d[5:2] + {3'b000, frame_rand[4]} : 4'd0;
    wire [3:0] glow = !glow_on ? 4'd0 : (scene == SC_COUNT) ? {1'b0, glow_raw[3:1]} : glow_raw;

    // sky: blue near a planet with air, fading to black as we climb
    wire [3:0] sky_b_full = 4'd1 + {1'b0, y1[8:6]};
    wire [2:0] fade       = (scene == SC_LIFTOFF) ? t[8:6] : 3'd0;
    wire [3:0] sky_b      = tower_scene ? (sky_b_full >> fade) : 4'd0;
    wire [3:0] sky_g      = (tower_scene && y1[8] && fade == 3'd0) ? 4'd1 : 4'd0;

    // -- put it together, nearest thing first
    reg [11:0] glass_colour;
    always @(*) begin
        // far to near
        glass_colour = {4'd0, sky_g, sky_b};
        case (star1)
            2'd1: glass_colour = 12'h99A;
            2'd2: glass_colour = 12'hFFF;
            2'd3: glass_colour = 12'h7AF;
            default: ;
        endcase
        if (tower)  glass_colour = tower_bar ? 12'h667 : 12'h112;
        if (arm)    glass_colour = 12'h556;
        if (beacon) glass_colour = 12'hF22;
        if (rim1)   glass_colour = ground ? 12'h37C : 12'h46A;
        if (body1) begin
            if (ground)
                glass_colour = city1 ? 12'hFD6 : (stripe1 ? 12'h143 : 12'h132);
            else if (shadow1)
                glass_colour = equator1 ? 12'h321 : 12'h210;
            else
                glass_colour = equator1 ? (band1 ? 12'hDA6 : 12'hC84) : (band1 ? 12'hA63 : 12'h974);
        end
        // engine glow brightens whatever is there
        if (glow > glass_colour[11:8])          glass_colour[11:8] = glow;
        if ({1'b0, glow[3:1]} > glass_colour[7:4]) glass_colour[7:4]  = {1'b0, glow[3:1]};
        if (reticle)    glass_colour = 12'h0CC;
        if (alert_edge) glass_colour = 12'hFA0;
        if (banner)     glass_colour = (scene == SC_SAFE) ? (t[4] ? 12'h850 : 12'h420)
                                                           : (t[4] ? 12'hA00 : 12'h300);
        if (banner && txt1) glass_colour = 12'hFFF;
        if (big1)       glass_colour = 12'hFF0;
    end

    reg [11:0] colour;
    always @(*) begin
        if (!act1)
            colour = 12'h000;                                   // must be black outside the picture
        else if (glass)
            colour = glass_colour;
        else if (txt1)
            colour = top_bar ? 12'hFFF : 12'h0FC;
        else if (lamp_state)
            colour = state_colour;
        else if (lamp_link)
            colour = link_lost ? (blink ? 12'hF00 : 12'h300) : 12'h0C0;
        else if (scr_c_edge || scr_l_edge || scr_r_edge)
            colour = 12'h0AA;
        else if (bar_cap)
            colour = 12'hFB0;
        else if (bar_on)
            colour = 12'h0C4;
        else if (lamp_lit)
            colour = (y1[6:4] == 3'd0) ? 12'hE22 : (y1[6:4] == 3'd1) ? 12'hEA0 : 12'h0C4;
        else if (lamp_in)
            colour = 12'h122;
        else if (scr_c || scr_l || scr_r)
            colour = 12'h011;
        else if ((dash && y1 < 10'd363) || (top_bar && y1 >= 10'd38))
            colour = 12'h0AC;                                   // glowing trim lines
        else if (strut_edge && !top_bar && !dash)
            colour = 12'h667;
        else
            colour = 12'h223;                                   // cockpit body
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            vga_r  <= 4'd0;  vga_g <= 4'd0;  vga_b <= 4'd0;
            vga_hs <= 1'b1;  vga_vs <= 1'b1;
        end else if (pix_en) begin
            vga_r  <= colour[11:8];
            vga_g  <= colour[7:4];
            vga_b  <= colour[3:0];
            vga_hs <= hs1;
            vga_vs <= vs1;
        end
    end

endmodule
