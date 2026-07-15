module tb_saturating_counter;
    logic clk = 0;
    logic rst_n = 0;
    logic enable = 1;
    logic up = 1;
    logic [7:0] count;
    int errors = 0;
    saturating_counter dut (.*);
    always #2 clk = ~clk;
    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1;
        repeat (260) @(posedge clk);
        #1; if (count !== 8'hFF) begin errors++; $display("TEST_FAILED upper saturation"); end
        up = 0;
        repeat (260) @(posedge clk);
        #1; if (count !== 8'h00) begin errors++; $display("TEST_FAILED lower saturation"); end
        enable = 0;
        repeat (2) @(posedge clk);
        #1; if (count !== 8'h00) begin errors++; $display("TEST_FAILED disabled hold"); end
        if (errors == 0) $display("SATURATING_COUNTER_SCOREBOARD_PASS");
        else $display("TEST_FAILED SATURATING_COUNTER errors=%0d", errors);
        $finish;
    end
endmodule
