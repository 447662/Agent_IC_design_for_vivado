module tb_priority_encoder;
    import uvm_pkg::*;
    import priority_encoder_pkg::*;
    logic clk = 1'b0;
    priority_encoder_if priority_vif(clk);
    priority_encoder dut (
        .req(priority_vif.req),
        .index(priority_vif.index),
        .valid(priority_vif.valid)
    );
    priority_encoder_sva checks (
        .clk(clk), .req(priority_vif.req), .index(priority_vif.index), .valid(priority_vif.valid)
    );
    always #5 clk = ~clk;
    initial begin
        priority_vif.req = '0;
        uvm_config_db#(virtual priority_encoder_if)::set(null, "*", "vif", priority_vif);
        run_test("priority_test");
    end
endmodule
