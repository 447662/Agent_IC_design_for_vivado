module tb_edge_detector;
    logic clk = 0;
    logic rst_n = 0;
    logic signal_i = 0;
    logic pulse_o;
    int errors = 0;
    edge_detector dut (.*);
    always #5 clk = ~clk;
    property pulse_is_single_cycle;
        @(posedge clk) disable iff (!rst_n) pulse_o |=> !pulse_o;
    endproperty
    assert property (pulse_is_single_cycle)
        else begin errors++; $display("EDGE_DETECTOR_SVA_FAIL"); end
    task drive_and_check(bit value, bit expected);
        @(negedge clk); signal_i = value;
        @(posedge clk); #1;
        if (pulse_o !== expected) begin errors++; $display("TEST_FAILED expected=%0d actual=%0d", expected, pulse_o); end
    endtask
    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1;
        drive_and_check(0, 0);
        drive_and_check(1, 1);
        drive_and_check(1, 0);
        drive_and_check(0, 0);
        drive_and_check(1, 1);
        if (errors == 0) $display("EDGE_DETECTOR_SCOREBOARD_PASS");
        else $display("TEST_FAILED EDGE_DETECTOR errors=%0d", errors);
        $finish;
    end
endmodule
