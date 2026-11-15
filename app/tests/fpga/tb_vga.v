// tb_vga.v
// SIMULATION ONLY. Passing here does not mean the monitor shows a picture.
//
// VGA step 1: the 640 x 480 timing and the test pattern.
//   - line length 800 pixels, sync pulse 96 pixels, active low
//   - frame length 525 lines, sync pulse 2 lines, active low
//   - exactly 640 x 480 visible pixels per frame, black everywhere else
//   - the four border corners are white, the first bar is white, the last
//     bar is black, the centre square shows the state colour and blinks to
//     black when the link is lost

`timescale 1ns / 1ps

module tb_vga;

    reg clk = 1'b0;
    always #10 clk = ~clk;           // 50 MHz

    integer errors = 0;

    task check;
        input         ok;
        input [639:0] what;
        begin
            if (!ok) begin
                errors = errors + 1;
                $display("FAIL  %0s  (t=%0t)", what, $time);
            end else begin
                $display("ok    %0s", what);
            end
        end
    endtask

    reg        rst_n = 1'b0;
    reg  [2:0] state = 3'd0;
    reg        link_lost = 1'b0;
    reg        blink = 1'b0;
    wire [3:0] r, g, b;
    wire       hs, vs;

    vga_cockpit dut (
        .clk(clk), .rst_n(rst_n),
        .state(state), .link_lost(link_lost), .blink(blink),
        .vga_r(r), .vga_g(g), .vga_b(b), .vga_hs(hs), .vga_vs(vs)
    );

    wire [11:0] rgb = {r, g, b};

    // ---------------------------------------------------------- measure the sync pulses (in 50 MHz clocks)
    integer clk_n = 0;
    integer hs_fall = -1, hs_period = 0, hs_width = 0, hs_bad = 0, hs_count = 0;
    integer vs_fall = -1, vs_period = 0, vs_width = 0, vs_count = 0;
    reg     hs_d = 1'b1, vs_d = 1'b1;

    always @(posedge clk) begin
        clk_n <= clk_n + 1;
        hs_d  <= hs;
        vs_d  <= vs;
        if (hs_d && !hs) begin
            if (hs_fall >= 0) begin
                hs_period = clk_n - hs_fall;
                if (hs_period != 1600) hs_bad = hs_bad + 1;
            end
            hs_fall  = clk_n;
            hs_count = hs_count + 1;
        end
        if (!hs_d && hs) begin
            hs_width = clk_n - hs_fall;
            if (hs_width != 192) hs_bad = hs_bad + 1;
        end
        if (vs_d && !vs) begin
            if (vs_fall >= 0) vs_period = clk_n - vs_fall;
            vs_fall  = clk_n;
            vs_count = vs_count + 1;
        end
        if (!vs_d && vs) vs_width = clk_n - vs_fall;
    end

    // ---------------------------------------------------------- count pixels
    // The outputs are one pixel behind the counters, so sample the counter
    // position that produced the colour now on the pins.
    reg [9:0] px = 0, py = 0;
    reg       pact = 0;
    integer   lit_outside = 0;
    integer   visible = 0;
    reg [11:0] at_corner_tl, at_corner_br, at_bar0, at_bar7, at_centre;

    always @(posedge clk) begin
        if (dut.pix_en) begin
            px   <= dut.x;
            py   <= dut.y;
            pact <= dut.active;
        end
    end

    always @(negedge clk) begin
        if (rst_n && !dut.pix_en) begin          // pins hold the pixel (px, py)
            if (pact) visible = visible + 1;
            if (!pact && rgb !== 12'h000) lit_outside = lit_outside + 1;
            if (px == 0   && py == 0)   at_corner_tl = rgb;
            if (px == 639 && py == 479) at_corner_br = rgb;
            if (px == 40  && py == 100) at_bar0      = rgb;
            if (px == 600 && py == 100) at_bar7      = rgb;
            if (px == 320 && py == 240) at_centre    = rgb;
        end
    end

    task wait_frames;
        input integer n;
        integer start;
        begin
            start = vs_count;
            while (vs_count < start + n) @(posedge clk);
        end
    endtask

    initial begin
        repeat (5) @(posedge clk);
        rst_n = 1'b1;

        wait_frames(1);                  // settle to a frame boundary
        visible = 0;
        wait_frames(1);
        check(visible == 640 * 480, "exactly 640 x 480 visible pixels in one frame");
        wait_frames(1);

        check(hs_bad == 0 && hs_period == 1600 && hs_width == 192,
              "every line: 800 pixels long, sync pulse 96 pixels, active low");
        check(vs_period == 1600 * 525, "frame is 525 lines long");
        check(vs_width == 1600 * 2, "vertical sync pulse is 2 lines, active low");
        check(lit_outside == 0, "colour is black everywhere outside the visible picture");

        check(at_corner_tl === 12'hFFF && at_corner_br === 12'hFFF, "border corners are white");
        check(at_bar0 === 12'hFFF, "first colour bar is white");
        check(at_bar7 === 12'h000, "last colour bar is black");
        check(at_centre === 12'h888, "centre square is grey in IDLE");

        state = 3'd3;
        wait_frames(1);
        check(at_centre === 12'h0F0, "centre square is green in RUNNING");

        link_lost = 1'b1; blink = 1'b1;
        wait_frames(1);
        check(at_centre === 12'h000, "centre square blinks to black when the link is lost");
        blink = 1'b0;
        wait_frames(1);
        check(at_centre === 12'h0F0, "and back to the state colour on the other half of the blink");

        if (errors == 0) $display("SIMULATION PASS: tb_vga (simulation only, not a board test)");
        else             $display("SIMULATION FAIL: tb_vga, %0d error(s)", errors);
        $finish;
    end

endmodule
