// vga_sync.v
// VGA timing for 640 x 480 at 60 Hz.
//
// The screen is drawn one pixel at a time, left to right, top to bottom.
// One pixel lasts two 50 MHz clocks (25 MHz pixel rate; the standard asks
// for 25.175 MHz, monitors accept 25). `pix_en` is high on the clock where
// the pixel counters move, so everything stays on the one 50 MHz clock.
//
//   One line  = 640 visible + 16 front porch + 96 sync + 48 back porch = 800 pixels
//   One frame = 480 visible + 10 front porch +  2 sync + 33 back porch = 525 lines
//   Both sync pulses are active low.
//
// Display only. Nothing here touches the mission.

module vga_sync (
    input  wire       clk,          // 50 MHz
    input  wire       rst_n,
    output reg        pix_en,       // one pulse per pixel
    output reg  [9:0] x,            // 0..799, visible 0..639
    output reg  [9:0] y,            // 0..524, visible 0..479
    output wire       active,       // this pixel is on the visible screen
    output wire       hsync,        // active low
    output wire       vsync,        // active low
    output wire       frame_start   // one pulse (with pix_en) at pixel 0,0
);

    localparam [9:0] H_VISIBLE = 10'd640, H_FRONT = 10'd16, H_SYNC = 10'd96, H_TOTAL = 10'd800;
    localparam [9:0] V_VISIBLE = 10'd480, V_FRONT = 10'd10, V_SYNC = 10'd2,  V_TOTAL = 10'd525;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pix_en <= 1'b0;
            x      <= 10'd0;
            y      <= 10'd0;
        end else begin
            pix_en <= ~pix_en;
            if (pix_en) begin
                if (x == H_TOTAL - 10'd1) begin
                    x <= 10'd0;
                    y <= (y == V_TOTAL - 10'd1) ? 10'd0 : y + 10'd1;
                end else begin
                    x <= x + 10'd1;
                end
            end
        end
    end

    assign active = (x < H_VISIBLE) && (y < V_VISIBLE);
    assign hsync  = ~((x >= H_VISIBLE + H_FRONT) && (x < H_VISIBLE + H_FRONT + H_SYNC));
    assign vsync  = ~((y >= V_VISIBLE + V_FRONT) && (y < V_VISIBLE + V_FRONT + V_SYNC));
    assign frame_start = pix_en && (x == 10'd0) && (y == 10'd0);

endmodule
