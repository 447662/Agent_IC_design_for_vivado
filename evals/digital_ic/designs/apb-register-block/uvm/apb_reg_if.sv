interface apb_reg_if(input logic PCLK);
    logic PRESETn;
    logic PSEL;
    logic PENABLE;
    logic PWRITE;
    logic [7:0] PADDR;
    logic [31:0] PWDATA;
    logic [3:0] PSTRB;
    logic [31:0] PRDATA;
    logic PREADY;
    logic PSLVERR;
    logic [31:0] status_i;
    logic [31:0] control_o;

    clocking drv_cb @(posedge PCLK);
        default input #1step output #1ns;
        output PSEL, PENABLE, PWRITE, PADDR, PWDATA, PSTRB;
        input PRESETn, PRDATA, PREADY, PSLVERR;
    endclocking
    clocking mon_cb @(posedge PCLK);
        default input #1step;
        input PRESETn, PSEL, PENABLE, PWRITE, PADDR, PWDATA, PSTRB;
        input PRDATA, PREADY, PSLVERR, status_i, control_o;
    endclocking
endinterface
