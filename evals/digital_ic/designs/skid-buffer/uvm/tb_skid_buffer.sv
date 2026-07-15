module tb_skid_buffer;
    logic clk = 0;
    logic rst_n = 0;
    logic s_valid = 0;
    logic s_ready;
    logic [7:0] s_data = 0;
    logic m_valid;
    logic m_ready = 0;
    logic [7:0] m_data;
    int errors = 0;
    skid_buffer dut (.*);
    always #5 clk = ~clk;
    property output_stable_while_stalled;
        @(posedge clk) disable iff (!rst_n) m_valid && !m_ready |=> $stable(m_data) && m_valid;
    endproperty
    assert property (output_stable_while_stalled)
        else begin errors++; $display("SKID_BUFFER_SVA_FAIL"); end
    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1;
        @(negedge clk); m_ready = 1; s_valid = 1; s_data = 8'hA1;
        @(posedge clk); #1;
        if (!m_valid || m_data != 8'hA1) errors++;
        @(negedge clk); m_ready = 0; s_valid = 1; s_data = 8'hB2;
        repeat (2) begin
            @(posedge clk); #1;
            if (s_ready || !m_valid || m_data != 8'hA1) errors++;
        end
        @(negedge clk); m_ready = 1;
        @(posedge clk); #1;
        if (!m_valid || m_data != 8'hB2) errors++;
        @(negedge clk); s_valid = 0;
        @(posedge clk); #1;
        if (m_valid) errors++;
        if (errors == 0) $display("SKID_BUFFER_SCOREBOARD_PASS");
        else $display("TEST_FAILED SKID_BUFFER errors=%0d", errors);
        $finish;
    end
endmodule
