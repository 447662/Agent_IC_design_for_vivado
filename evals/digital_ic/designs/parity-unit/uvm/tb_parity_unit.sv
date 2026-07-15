module tb_parity_unit;
    logic [15:0] data_i;
    logic parity_i;
    logic parity_o;
    logic error_o;
    int errors = 0;
    parity_unit dut (.*);
    initial begin
        for (int value = 0; value < 256; value++) begin
            data_i = {8'hA5, value[7:0]};
            parity_i = ^data_i;
            #1;
            if (parity_o !== (^data_i) || error_o !== 0) errors++;
            parity_i = ~(^data_i);
            #1;
            if (error_o !== 1) errors++;
        end
        if (errors == 0) $display("PARITY_UNIT_SCOREBOARD_PASS");
        else $display("TEST_FAILED PARITY_UNIT errors=%0d", errors);
        $finish;
    end
endmodule
