module tb_gray_codec;
    logic [7:0] binary_i;
    logic [7:0] gray_o;
    logic [7:0] binary_o;
    int errors = 0;
    gray_codec dut (.*);
    initial begin
        for (int value = 0; value < 256; value++) begin
            binary_i = value[7:0];
            #1;
            if (gray_o !== (binary_i ^ (binary_i >> 1))) errors++;
            if (binary_o !== binary_i) errors++;
        end
        if (errors == 0) $display("GRAY_CODEC_SCOREBOARD_PASS");
        else $display("TEST_FAILED GRAY_CODEC errors=%0d", errors);
        $finish;
    end
endmodule
