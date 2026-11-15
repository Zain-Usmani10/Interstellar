// vga_cockpit.v
// The shuttle's cockpit picture on the VGA monitor.
//
// STEP 1 (this version): a test pattern that proves the VGA pins, the
// timing and the monitor.
//   - a one-pixel white border on all four edges (if any edge is missing,
//     the picture is shifted or cropped)
//   - eight vertical colour bars: white yellow cyan green magenta red blue black
//   - a square in the middle whose colour is the mission state, so there is
//     one live board value on screen:
//       idle grey, loaded/armed blue, running green, safe amber,
//       complete white, aborted red
//   - the square blinks to black once a second when the link is lost
//
// Display only. It reads board values and drives the monitor; nothing here
// feeds back into the mission. Colours are 4 bits per channel.

module vga_cockpit (
    input  wire       clk,
    input  wire       rst_n,

    // board values (same registers the STATUS frame reports)
    input  wire [2:0] state,
    input  wire       link_lost,
    input  wire       blink,            // 1 Hz square wave

    output reg  [3:0] vga_r,
    output reg  [3:0] vga_g,
    output reg  [3:0] vga_b,
    output reg        vga_hs,
    output reg        vga_vs
);

    wire       pix_en;
    wire [9:0] x, y;
    wire       active, hsync, vsync, frame_start;

    vga_sync u_sync (
        .clk         (clk),
        .rst_n       (rst_n),
        .pix_en      (pix_en),
        .x           (x),
        .y           (y),
        .active      (active),
        .hsync       (hsync),
        .vsync       (vsync),
        .frame_start (frame_start)
    );

    // ------------------------------------------------------------ what colour is this pixel
    wire border = (x == 10'd0) || (x == 10'd639) || (y == 10'd0) || (y == 10'd479);
    wire square = (x >= 10'd256) && (x < 10'd384) && (y >= 10'd176) && (y < 10'd304);

    // Eight bars, 80 pixels each. Bar number 0..7 counts down the colours:
    // bit 2 = green, bit 1 = red, bit 0 = blue, inverted so bar 0 is white.
    wire [2:0] bar = ~(x[9:4] / 3'd5);

    reg [11:0] state_colour;            // {r, g, b}
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

    reg [11:0] colour;
    always @(*) begin
        if (!active)
            colour = 12'h000;                   // must be black outside the picture
        else if (border)
            colour = 12'hFFF;
        else if (square)
            colour = (link_lost && blink) ? 12'h000 : state_colour;
        else
            colour = {{4{bar[1]}}, {4{bar[2]}}, {4{bar[0]}}};
    end

    // Registered outputs: clean edges on the pins, sync delayed with the colour.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            vga_r  <= 4'd0;
            vga_g  <= 4'd0;
            vga_b  <= 4'd0;
            vga_hs <= 1'b1;
            vga_vs <= 1'b1;
        end else if (pix_en) begin
            vga_r  <= colour[11:8];
            vga_g  <= colour[7:4];
            vga_b  <= colour[3:0];
            vga_hs <= hsync;
            vga_vs <= vsync;
        end
    end

endmodule
