module tb_pulse_stretcher;
    logic clk = 0;
    logic rst_n = 0;
    logic trigger = 0;
    logic pulse;
    int errors = 0;
    pulse_stretcher dut (.*);
    always #5 clk = ~clk;
    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1;
        @(negedge clk); trigger = 1;
        @(posedge clk); #1; trigger = 0;
        repeat (4) begin
            if (!pulse) errors++;
            @(posedge clk); #1;
        end
        if (pulse) errors++;
        @(negedge clk); trigger = 1;
        @(posedge clk); #1; trigger = 0;
        repeat (2) @(posedge clk);
        @(negedge clk); trigger = 1;
        @(posedge clk); #1; trigger = 0;
        repeat (4) begin
            if (!pulse) errors++;
            @(posedge clk); #1;
        end
        if (pulse) errors++;
        if (errors == 0) $display("PULSE_STRETCHER_SCOREBOARD_PASS");
        else $display("TEST_FAILED PULSE_STRETCHER errors=%0d", errors);
        $finish;
    end
endmodule
