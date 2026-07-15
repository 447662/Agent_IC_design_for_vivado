interface priority_encoder_if(input logic clk);
    logic [7:0] req;
    logic [2:0] index;
    logic valid;
    clocking drv_cb @(posedge clk);
        default input #1step output #1ns;
        output req;
        input index, valid;
    endclocking
    clocking mon_cb @(posedge clk);
        default input #1step;
        input req, index, valid;
    endclocking
endinterface
