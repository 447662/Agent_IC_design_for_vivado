module tb_clock_enable_divider;
    logic clk = 0;
    logic rst_n = 0;
    logic [7:0] divisor = 3;
    logic tick;
    int errors = 0;
    int cycles_since_tick = 0;
    int ticks = 0;
    clock_enable_divider dut (.*);
    always #5 clk = ~clk;
    initial begin
        repeat (2) @(posedge clk);
        @(negedge clk); rst_n = 1;
        repeat (15) begin
            @(posedge clk); #1;
            cycles_since_tick++;
            if (tick) begin
                ticks++;
                if (cycles_since_tick != 3) errors++;
                cycles_since_tick = 0;
            end
        end
        if (ticks != 5) errors++;
        divisor = 1;
        repeat (4) begin
            @(posedge clk); #1;
            if (!tick) errors++;
        end
        if (errors == 0) $display("CLOCK_ENABLE_DIVIDER_SCOREBOARD_PASS");
        else $display("TEST_FAILED CLOCK_ENABLE_DIVIDER errors=%0d", errors);
        $finish;
    end
endmodule
