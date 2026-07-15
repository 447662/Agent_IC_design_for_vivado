module tb_apb_register_block;
    import uvm_pkg::*;
    import apb_reg_pkg::*;
    logic PCLK = 1'b0;
    apb_reg_if apb_vif(PCLK);

    apb_register_block dut (
        .PCLK(PCLK), .PRESETn(apb_vif.PRESETn), .PSEL(apb_vif.PSEL),
        .PENABLE(apb_vif.PENABLE), .PWRITE(apb_vif.PWRITE), .PADDR(apb_vif.PADDR),
        .PWDATA(apb_vif.PWDATA), .PSTRB(apb_vif.PSTRB), .PRDATA(apb_vif.PRDATA),
        .PREADY(apb_vif.PREADY), .PSLVERR(apb_vif.PSLVERR),
        .status_i(apb_vif.status_i), .control_o(apb_vif.control_o)
    );
    apb_reg_sva checks (
        .PCLK(PCLK), .PRESETn(apb_vif.PRESETn), .PSEL(apb_vif.PSEL),
        .PENABLE(apb_vif.PENABLE), .PADDR(apb_vif.PADDR),
        .PREADY(apb_vif.PREADY), .PSLVERR(apb_vif.PSLVERR)
    );
    always #5 PCLK = ~PCLK;
    initial begin
        apb_vif.PRESETn = 0;
        apb_vif.PSEL = 0;
        apb_vif.PENABLE = 0;
        apb_vif.PWRITE = 0;
        apb_vif.PADDR = '0;
        apb_vif.PWDATA = '0;
        apb_vif.PSTRB = '0;
        apb_vif.status_i = 32'hA5A5_5A5A;
        repeat (4) @(posedge PCLK);
        @(negedge PCLK);
        apb_vif.PRESETn = 1;
    end
    initial begin
        uvm_config_db#(virtual apb_reg_if)::set(null, "*", "vif", apb_vif);
        run_test("apb_reg_test");
    end
endmodule
