// tb_vga.v
// SIMULATION ONLY. Passing here does not mean the monitor shows a picture.
//
// The VGA cockpit:
//   - line length 800 pixels, sync pulse 96 pixels, active low
//   - frame length 525 lines, sync pulse 2 lines, active low
//   - exactly 640 x 480 visible pixels per frame, black everywhere else
//   - the picture is not blank
//   - the picture follows the mission state (docked, countdown, cruise, safe)
// To keep the run short it uses four stars.
// What the scenes look like is checked by eye, not here.

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
    reg        departed = 1'b0;
    reg [31:0] tick_count = 32'd0;
    wire [3:0] r, g, b;
    wire       hs, vs;

    vga_cockpit #(.STARS(4)) dut (
        .clk(clk), .rst_n(rst_n),
        .state(state), .departed(departed), .captured(1'b0),
        .tick_count(tick_count), .departure_tick(32'd500), .trip_ticks(32'd6000),
        .trip_days_valid(1'b1), .days_to_arrival(32'd111), .fuel_g(32'd4781982),
        .link_seen(1'b1), .link_lost(link_lost),
        .session_open(1'b1), .masked_seen(1'b0), .no_majority_seen(1'b0), .rx_error_seen(1'b0),
        .blink(blink),
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
    // The colour on the pins is two pixels behind the counters; `shown` is
    // the "visible" flag of the pixel that is on the pins now.
    reg     shown = 0;
    integer lit_outside = 0;
    integer visible = 0;
    integer lit_inside = 0;

    always @(posedge clk) begin
        if (dut.pix_en) shown <= dut.act1;
    end

    always @(negedge clk) begin
        if (rst_n && !dut.pix_en) begin
            if (shown) visible = visible + 1;
            if (shown && rgb !== 12'h000) lit_inside = lit_inside + 1;
            if (!shown && rgb !== 12'h000) lit_outside = lit_outside + 1;
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
        check(lit_inside > 100000, "the picture is not blank");

        check(dut.scene == 3'd0, "idle shows the docked picture");
        state = 3'd3;
        wait_frames(2);
        check(dut.scene == 3'd1, "running before the departure burn shows the countdown");
        departed = 1'b1;  tick_count = 32'd1500;
        wait_frames(2);
        check(dut.scene == 3'd3, "after liftoff it shows the cruise picture");
        state = 3'd4;
        wait_frames(1);
        check(dut.scene == 3'd7, "safe mode shows the alert picture");

        if (errors == 0) $display("SIMULATION PASS: tb_vga (simulation only, not a board test)");
        else             $display("SIMULATION FAIL: tb_vga, %0d error(s)", errors);
        $finish;
    end

endmodule
