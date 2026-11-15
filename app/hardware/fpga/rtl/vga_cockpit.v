// vga_cockpit.v
// The shuttle's cockpit picture on the VGA monitor: the pilot's view through
// the windshield, with a dashboard underneath. 640 x 480, 4 bits per colour.
//
// The picture follows the real mission on this board:
//   idle / loaded / armed            docked at the launch tower
//   running, before departure burn   countdown (engine glow in the last 2 s)
//   after the departure burn         liftoff for about 7 s, then cruise,
//                                    fast cruise in the middle half of the
//                                    trip, and the destination growing in the
//                                    last eighth
//   capture burn done / complete     arrived: the planet fills the view
//   safe / aborted                   alert view with a banner
//   link lost                        red "NO LINK" banner over whatever is shown
//
// Every number and lamp is a board value:
//   centre screen  state, T-minus, days (trip_clock), fuel in kg, link
//   left screen    fuel history: one column per 128 mission ticks, plus a
//                  dotted line at the fuel level now. The scale is the first
//                  power of two that fits the starting fuel.
//   right screen   row 1 (red)   link lost, safe, aborted, masked fault seen,
//                                no-majority seen, receive error seen
//                  row 2 (amber) plan loaded, armed, running, departure burn,
//                                capture burn, complete, session open, trip days set
//                  rows 3-4 (green) trip progress, 16 lamps
//   top right      mission state colour, link
//
// Nothing is stored as pictures. Every pixel is worked out as it is drawn:
//   stars   vga_stars.v (points that fly outward from the centre)
//   planet  one circle test, (dx*dx + dy*dy) < r*r, with bands and a shadow
//   cockpit rectangles and two slanted struts
//   words   vga_font.v + vga_text.v
//
// Two steps per pixel: step 1 does the heavy sums and stores the results,
// step 2 picks the colour. Display only: nothing here feeds the mission.

module vga_cockpit #(
    parameter integer STARS = 48
) (
    input  wire        clk,
    input  wire        rst_n,

    // live board values
    input  wire [2:0]  state,
    input  wire        departed,               // departure burn done (mask bit 0)
    input  wire        captured,               // capture burn done (mask bit 1)
    input  wire [31:0] tick_count,
    input  wire [31:0] departure_tick,
    input  wire [31:0] trip_ticks,             // arrival tick - departure tick
    input  wire        trip_days_valid,
    input  wire [31:0] days_to_arrival,
    input  wire [31:0] fuel_g,
    input  wire        link_seen,
    input  wire        link_lost,
    input  wire        session_open,
    input  wire        masked_seen,
    input  wire        no_majority_seen,
    input  wire        rx_error_seen,
    input  wire        blink,                  // 1 Hz square wave

    output reg  [3:0]  vga_r,
    output reg  [3:0]  vga_g,
    output reg  [3:0]  vga_b,
    output reg         vga_hs,
    output reg         vga_vs
);

    localparam [2:0] ST_IDLE = 3'd0, ST_LOADED = 3'd1, ST_ARMED = 3'd2, ST_RUNNING = 3'd3,
                     ST_SAFE = 3'd4, ST_COMPLETE = 3'd5, ST_ABORTED = 3'd6;

    // The pictures (the letters are the ones from the sample reel).
    localparam [2:0] SC_DOCKED = 3'd0, SC_COUNT = 3'd1, SC_LIFTOFF = 3'd2, SC_CRUISE = 3'd3,
                     SC_FAST   = 3'd4, SC_ARRIVAL = 3'd5, SC_SAFE   = 3'd7;

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

    // ------------------------------------------------------------ mission values, tidied once per frame
    wire docked  = (state == ST_IDLE) || (state == ST_LOADED) || (state == ST_ARMED);
    wire arrived = captured || (state == ST_COMPLETE);

    wire [31:0] since_dep = tick_count - departure_tick;
    wire [31:0] until_dep = departure_tick - tick_count;

    // How many places to shift fuel (grams) right so the starting fuel is 32..63.
    function [4:0] fuel_shift;
        input [31:0] v;
        integer i;
        reg [5:0] top;
        begin
            top = 6'd0;
            for (i = 0; i < 32; i = i + 1)
                if (v[i]) top = i[5:0];
            fuel_shift = (top > 6'd5) ? (top[4:0] - 5'd5) : 5'd0;
        end
    endfunction

    reg [7:0]  fc;                // frame counter, for blinking things
    reg [15:0] frame_rand;        // a new random number every frame
    reg [9:0]  el;                // ticks since the departure burn, stops at 1023
    reg [13:0] cd;                // ticks until the departure burn, stops at 9999
    reg [8:0]  at;                // frames since the arrival picture began, stops at 359
    reg [31:0] fuel_start;        // fuel while docked = the plan's starting fuel
    reg [4:0]  fuel_sh;
    reg [5:0]  lvl;               // fuel now, as a height 0..63 on the graph

    wire [31:0] fuel_scaled = fuel_g >> fuel_sh;

    // ------------------------------------------------------------ which picture
    reg [4:0] prog;               // trip progress, 0..16

    // Worked out here, then held steady for one whole frame (scene, arrived_q).
    reg [2:0] scene_next;
    reg [2:0] scene;
    reg       arrived_q;
    always @(*) begin
        if (docked)                                   scene_next = SC_DOCKED;
        else if (state == ST_SAFE || state == ST_ABORTED) scene_next = SC_SAFE;
        else if (arrived)                             scene_next = SC_ARRIVAL;
        else if (!departed)                           scene_next = SC_COUNT;
        else if (el < 10'd720)                        scene_next = SC_LIFTOFF;
        else if (prog >= 5'd14)                       scene_next = SC_ARRIVAL;
        else if (prog >= 5'd4 && prog < 5'd12)        scene_next = SC_FAST;
        else                                          scene_next = SC_CRUISE;
    end

    wire [8:0] lt = el[9:1];      // liftoff clock: 0..359 over the 7.2 s of liftoff

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            fc <= 8'd0;  frame_rand <= 16'hACE1;  scene <= SC_DOCKED;  arrived_q <= 1'b0;
            el <= 10'd0;  cd <= 14'd0;  at <= 9'd0;
            fuel_start <= 32'd0;  fuel_sh <= 5'd0;  lvl <= 6'd0;
        end else if (frame_tick) begin
            fc         <= fc + 8'd1;
            scene      <= scene_next;
            arrived_q  <= arrived;
            frame_rand <= {frame_rand[14:0], frame_rand[15] ^ frame_rand[13] ^ frame_rand[12] ^ frame_rand[10]};

            if (!departed)                     el <= 10'd0;
            else if (since_dep > 32'd1023)     el <= 10'd1023;
            else                               el <= since_dep[9:0];

            if (departed || tick_count >= departure_tick) cd <= 14'd0;
            else if (until_dep > 32'd9999)                cd <= 14'd9999;
            else                                          cd <= until_dep[13:0];

            if (scene != SC_ARRIVAL)   at <= 9'd0;
            else if (at != 9'd359)     at <= at + 9'd1;

            if (state == ST_LOADED || state == ST_ARMED) fuel_start <= fuel_g;
            fuel_sh <= fuel_shift(fuel_start);
            lvl     <= (|fuel_scaled[31:6]) ? 6'd63 : fuel_scaled[5:0];
        end
    end

    // ------------------------------------------------------------ trip progress and fuel history (once per mission tick)
    reg        tick0_prev;
    wire       tick_step = (tick_count[0] != tick0_prev);
    reg [27:0] prog_acc;
    wire [27:0] prog_step = trip_ticks[31:4];             // one lamp per sixteenth of the trip
    wire        prog_full = (prog_acc + 28'd1 >= prog_step);

    reg [5:0] hist [0:63];        // fuel height per column of the graph
    reg [6:0] hist_n;             // how many columns are filled

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tick0_prev <= 1'b0;  prog <= 5'd0;  prog_acc <= 28'd0;  hist_n <= 7'd0;
        end else begin
            tick0_prev <= tick_count[0];

            if (!departed) begin
                prog <= 5'd0;  prog_acc <= 28'd0;
            end else if (captured) begin
                prog <= 5'd16;
            end else if (tick_step && state == ST_RUNNING) begin
                if (prog_full) begin
                    prog_acc <= 28'd0;
                    if (prog != 5'd16) prog <= prog + 5'd1;
                end else begin
                    prog_acc <= prog_acc + 28'd1;
                end
            end

            if (docked)
                hist_n <= 7'd0;
            else if (state == ST_RUNNING && tick_step && tick_count[6:0] == 7'd1 && hist_n != 7'd64)
                hist_n <= hist_n + 7'd1;
        end
    end

    always @(posedge clk) begin
        if (state == ST_RUNNING && tick_step && tick_count[6:0] == 7'd1 && hist_n != 7'd64)
            hist[hist_n[5:0]] <= lvl;
    end

    // ------------------------------------------------------------ numbers as decimal digits
    wire [19:0] days_in = (days_to_arrival > 32'd9999) ? 20'd9999 : days_to_arrival[19:0];
    wire [26:0] fuel_in = (fuel_g > 32'd99999999) ? 27'd99999999 : fuel_g[26:0];
    wire [23:0] days_bcd, cd_bcd;
    wire [31:0] fuel_bcd;
    bin2bcd  u_bcd_days (.clk(clk), .rst_n(rst_n), .value(days_in),        .bcd(days_bcd));
    bin2bcd  u_bcd_cd   (.clk(clk), .rst_n(rst_n), .value({6'd0, cd}),     .bcd(cd_bcd));
    vga_bcd8 u_bcd_fuel (.clk(clk), .rst_n(rst_n), .value(fuel_in),        .bcd(fuel_bcd));

    // ------------------------------------------------------------ which words
    // Worked out here, then held steady for one whole frame (see the block below).
    reg [3:0] page_next;
    always @(*) begin
        case (state)
            ST_IDLE:     page_next = 4'd0;
            ST_LOADED:   page_next = 4'd1;
            ST_ARMED:    page_next = 4'd2;
            ST_SAFE:     page_next = 4'd8;
            ST_ABORTED:  page_next = 4'd9;
            default: begin
                if (arrived)                    page_next = 4'd7;
                else if (scene == SC_COUNT)     page_next = 4'd3;
                else if (scene == SC_LIFTOFF)   page_next = 4'd4;
                else if (scene == SC_ARRIVAL)   page_next = 4'd6;
                else                            page_next = 4'd5;
            end
        endcase
    end

    wire [1:0] banner_next = (state == ST_SAFE)    ? 2'd2 :
                             (state == ST_ABORTED) ? 2'd3 :
                             link_lost             ? 2'd1 : 2'd0;
    wire [1:0] link_next   = link_lost ? 2'd2 : link_seen ? 2'd1 : 2'd0;

    // The lamp rows of the right screen (bit 0 = leftmost lamp).
    wire [7:0] lamps_fault_next = {2'b00, rx_error_seen, no_majority_seen, masked_seen,
                                   (state == ST_ABORTED), (state == ST_SAFE), link_lost};
    wire [7:0] lamps_step_next  = {trip_days_valid, session_open, (state == ST_COMPLETE), captured, departed,
                                   (state == ST_RUNNING),
                                   (state == ST_ARMED || state == ST_RUNNING || state == ST_COMPLETE),
                                   (state != ST_IDLE)};

    reg [3:0] page;
    reg [1:0] banner_sel, link_sel;
    reg [7:0] lamps_fault, lamps_step;
    reg       aborted_q;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            page <= 4'd0;  banner_sel <= 2'd0;  link_sel <= 2'd0;
            lamps_fault <= 8'd0;  lamps_step <= 8'd0;  aborted_q <= 1'b0;
        end else if (frame_tick) begin
            page        <= page_next;
            banner_sel  <= banner_next;
            link_sel    <= link_next;
            lamps_fault <= lamps_fault_next;
            lamps_step  <= lamps_step_next;
            aborted_q   <= (state == ST_ABORTED);
        end
    end

    // ------------------------------------------------------------ per-scene settings
    // Launch shake: a random 0..3 pixel jolt for the first three seconds.
    wire [9:0] rise  = (scene == SC_LIFTOFF) ? {2'b00, lt[8:1]} : 10'd0;
    wire [9:0] shake = (scene == SC_LIFTOFF && lt < 9'd180) ? {8'd0, frame_rand[1:0]} : 10'd0;
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
                star_speed = (lt < 9'd150) ? 2'd0 : 2'd1;
            end
            SC_CRUISE: begin
                star_speed = 2'd2;
                ccx = 12'sd430;  ccy = 12'sd170;  cr = 10'd10;       // far-off destination
            end
            SC_FAST: begin
                star_speed = 2'd3;
            end
            SC_ARRIVAL: begin
                star_speed = arrived_q ? 2'd0 : 2'd1;
                cr = 10'd20 + {2'b00, at[8:1]};                         // grows as we approach
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

    // Words: the text grid.
    wire       txt_cell_on;
    wire [5:0] txt_code_raw;
    vga_text u_text (
        .page(page), .banner(banner_sel), .link(link_sel),
        .row(y[8:4]), .col(x[9:4]), .on(txt_cell_on), .code(txt_code_raw)
    );

    reg [5:0] txt_code;                       // fill in the live digits
    always @(*) begin
        case (txt_code_raw)
            6'd44:   txt_code = trip_days_valid ? {2'b00, days_bcd[15:12]} : 6'd37;   // days, or "-"
            6'd45:   txt_code = trip_days_valid ? {2'b00, days_bcd[11:8]}  : 6'd37;
            6'd46:   txt_code = trip_days_valid ? {2'b00, days_bcd[7:4]}   : 6'd37;
            6'd47:   txt_code = trip_days_valid ? {2'b00, days_bcd[3:0]}   : 6'd37;
            6'd48:   txt_code = {2'b00, fuel_bcd[31:28]};                             // fuel kg
            6'd49:   txt_code = {2'b00, fuel_bcd[27:24]};
            6'd50:   txt_code = {2'b00, fuel_bcd[23:20]};
            6'd51:   txt_code = {2'b00, fuel_bcd[19:16]};
            6'd52:   txt_code = {2'b00, fuel_bcd[15:12]};
            6'd53:   txt_code = {2'b00, cd_bcd[15:12]};                               // T-minus SS.t
            6'd54:   txt_code = {2'b00, cd_bcd[11:8]};
            6'd55:   txt_code = {2'b00, cd_bcd[7:4]};
            default: txt_code = txt_code_raw;
        endcase
    end

    wire [4:0] txt_bits;
    vga_font u_font_small (.code(txt_code), .row(y[3:1]), .bits(txt_bits));
    // Each cell is 8 x 8 font pixels (doubled on screen); the letter uses columns 1..5, rows 0..6.
    wire [2:0] fcx     = x[3:1];
    wire       txt_pix = txt_cell_on && (y[3:1] != 3'd7) && (fcx >= 3'd1) && (fcx <= 3'd5) &&
                         txt_bits[3'd5 - fcx];

    // Fuel history: look up the column this pixel is in (x 48..175, 2 pixels per column).
    wire [9:0] hx = x - 10'd48;
    reg  [5:0] hist_q;
    always @(posedge clk) hist_q <= hist[hx[6:1]];

    // Store the results, and the pixel position they belong to.
    reg [9:0]  x1, y1;
    reg        act1, hs1, vs1;
    reg [1:0]  star1;
    reg        body1, rim1, shadow1, band1, equator1, city1, stripe1, txt1;
    reg [5:0]  hist1;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            x1 <= 10'd0;  y1 <= 10'd0;  act1 <= 1'b0;  hs1 <= 1'b1;  vs1 <= 1'b1;
            star1 <= 2'd0;
            {body1, rim1, shadow1, band1, equator1, city1, stripe1, txt1} <= 8'd0;
            hist1 <= 6'd0;
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
            hist1    <= hist_q;
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

    // left screen: fuel history. One column per 128 mission ticks; the
    // height is the fuel left. A dotted line marks the fuel level now.
    wire       g_in    = scr_l && (x1 >= 10'd48) && (x1 < 10'd176) && (y1 >= 10'd384) && (y1 < 10'd448);
    wire [9:0] gx      = x1 - 10'd48;
    wire [9:0] gh      = 10'd448 - y1;                         // 1 at the bottom .. 64 at the top
    wire       g_col   = g_in && ({1'b0, gx[6:1]} < hist_n) && (gh <= {4'd0, hist1});
    wire       g_cap   = g_col && (gh + 10'd2 > {4'd0, hist1});
    wire       g_now   = g_in && (lvl != 6'd0) && (gh == {4'd0, lvl}) && x1[2];
    wire       g_grid  = g_in && ((y1[3:0] == 4'd0) || (x1[4:0] == 5'd16));

    // right screen: four rows of eight lamps, each one a board value.
    wire [2:0] lamp_c  = x1[6:4] - 3'd5;                       // column 0..7
    wire [1:0] lamp_r  = y1[5:4];                              // row 0..3
    wire       lamp_in = scr_r && (x1 >= 10'd464) && (x1 < 10'd592) && (y1 >= 10'd384) && (y1 < 10'd448) &&
                         (x1[3:0] >= 4'd3) && (x1[3:0] <= 4'd12) && (y1[3:0] >= 4'd3) && (y1[3:0] <= 4'd12);
    wire [4:0] lamp_num    = {1'b0, lamp_r[0], lamp_c};        // 0..15 across rows 2 and 3
    reg        lamp_on;
    always @(*) begin
        case (lamp_r)
            2'd0:    lamp_on = lamps_fault[lamp_c];
            2'd1:    lamp_on = lamps_step[lamp_c];
            default: lamp_on = (lamp_num < prog);
        endcase
    end
    wire       lamp_lit = lamp_in && lamp_on;

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
                   (y1 >= 10'd120 + drop) && (y1 < 10'd130 + drop) && fc[4];

    wire reticle_scene = (scene == SC_CRUISE) || (scene == SC_FAST) || (scene == SC_ARRIVAL);
    wire [9:0] adx = (x1 >= 10'd320) ? (x1 - 10'd320) : (10'd320 - x1);
    wire [9:0] ady = (y1 >= 10'd200) ? (y1 - 10'd200) : (10'd200 - y1);
    wire reticle = reticle_scene &&
                   (((y1 == 10'd200) && (adx >= 10'd14) && (adx < 10'd44)) ||
                    ((x1 == 10'd320) && (ady >= 10'd14) && (ady < 10'd44)) ||
                    ((adx == 10'd80) && (ady >= 10'd60) && (ady <= 10'd80)) ||      // corner brackets
                    ((ady == 10'd80) && (adx >= 10'd60) && (adx <= 10'd80)));

    wire banner  = (banner_sel != 2'd0) && (x1 >= 10'd128) && (x1 < 10'd512) && (y1 >= 10'd72) && (y1 < 10'd104);
    wire alert_edge = (scene == SC_SAFE) && fc[4] &&
                      ((y1 >= 10'd42 && y1 < 10'd48) || (y1 >= 10'd352 && y1 < 10'd358));

    // engine glow from below the windshield
    wire glow_on = ((scene == SC_COUNT) && (cd <= 14'd200)) || ((scene == SC_LIFTOFF) && (lt < 9'd240));
    wire [9:0] glow_d = y1 - 10'd280;
    wire [3:0] glow_raw = (y1 >= 10'd280) ? glow_d[5:2] + {3'b000, frame_rand[4]} : 4'd0;
    wire [3:0] glow = !glow_on ? 4'd0 : (scene == SC_COUNT) ? {1'b0, glow_raw[3:1]} : glow_raw;

    // sky: blue near a planet with air, fading to black as we climb
    wire [3:0] sky_b_full = 4'd1 + {1'b0, y1[8:6]};
    wire [2:0] fade       = (scene == SC_LIFTOFF) ? lt[8:6] : 3'd0;
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
        if (alert_edge) glass_colour = aborted_q ? 12'hF00 : 12'hFA0;
        if (banner)     glass_colour = (banner_sel == 2'd2) ? (fc[4] ? 12'h850 : 12'h420)
                                                             : (fc[4] ? 12'hA00 : 12'h300);
        if (banner && txt1) glass_colour = 12'hFFF;
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
        else if (g_cap)
            colour = 12'hFB0;
        else if (g_now)
            colour = 12'hFB0;
        else if (g_col)
            colour = 12'h075;
        else if (g_grid)
            colour = 12'h033;
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
