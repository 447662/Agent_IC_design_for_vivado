interface timer_if(input logic clk);
    logic rst_n;
    logic load;
    logic enable;
    logic [15:0] period;
    logic expired;

    clocking drv_cb @(posedge clk);
        default input #1step output #1ns;
        output load, enable, period;
        input rst_n, expired;
    endclocking

    clocking mon_cb @(posedge clk);
        default input #1step;
        input rst_n, load, enable, period, expired;
    endclocking
endinterface
