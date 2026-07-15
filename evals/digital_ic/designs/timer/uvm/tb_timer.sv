module tb_timer;
    import uvm_pkg::*;
    import timer_pkg::*;

    logic clk = 1'b0;
    timer_if timer_vif(clk);

    timer dut (
        .clk(clk),
        .rst_n(timer_vif.rst_n),
        .load(timer_vif.load),
        .enable(timer_vif.enable),
        .period(timer_vif.period),
        .expired(timer_vif.expired)
    );
    timer_sva checks (
        .clk(clk),
        .rst_n(timer_vif.rst_n),
        .period(timer_vif.period),
        .expired(timer_vif.expired)
    );

    always #5 clk = ~clk;

    initial begin
        timer_vif.rst_n = 1'b0;
        timer_vif.load = 1'b0;
        timer_vif.enable = 1'b0;
        timer_vif.period = '0;
        repeat (4) @(posedge clk);
        timer_vif.rst_n = 1'b1;
    end

    initial begin
        uvm_config_db#(virtual timer_if)::set(null, "*", "vif", timer_vif);
        run_test("timer_test");
    end
endmodule
