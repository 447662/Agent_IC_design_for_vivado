package apb_reg_pkg;
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    class apb_reg_item extends uvm_sequence_item;
        rand bit write;
        rand bit [7:0] address;
        rand bit [31:0] data;
        rand bit [3:0] strobes;
        bit [31:0] read_data;
        bit error;

        `uvm_object_utils_begin(apb_reg_item)
            `uvm_field_int(write, UVM_DEFAULT)
            `uvm_field_int(address, UVM_DEFAULT)
            `uvm_field_int(data, UVM_DEFAULT)
            `uvm_field_int(strobes, UVM_DEFAULT)
            `uvm_field_int(read_data, UVM_DEFAULT | UVM_NOCOMPARE)
            `uvm_field_int(error, UVM_DEFAULT | UVM_NOCOMPARE)
        `uvm_object_utils_end

        function new(string name = "apb_reg_item");
            super.new(name);
        endfunction
    endclass

    class apb_reg_sequence extends uvm_sequence #(apb_reg_item);
        `uvm_object_utils(apb_reg_sequence)
        function new(string name = "apb_reg_sequence");
            super.new(name);
        endfunction

        task send(bit write, bit [7:0] address, bit [31:0] data, bit [3:0] strobes);
            apb_reg_item item = apb_reg_item::type_id::create("item");
            start_item(item);
            item.write = write;
            item.address = address;
            item.data = data;
            item.strobes = strobes;
            finish_item(item);
        endtask

        task body();
            send(1, 8'h00, 32'h1122_3344, 4'hF);
            send(0, 8'h00, '0, '0);
            send(1, 8'h00, 32'hAABB_CCDD, 4'b0101);
            send(0, 8'h00, '0, '0);
            send(0, 8'h04, '0, '0);
            send(0, 8'h20, '0, '0);
            send(1, 8'h04, 32'hFFFF_FFFF, 4'hF);
        endtask
    endclass

    class apb_reg_driver extends uvm_driver #(apb_reg_item);
        `uvm_component_utils(apb_reg_driver)
        virtual apb_reg_if vif;
        function new(string name, uvm_component parent); super.new(name, parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db#(virtual apb_reg_if)::get(this, "", "vif", vif))
                `uvm_fatal("NOVIF", "apb_reg_if was not configured")
        endfunction
        task run_phase(uvm_phase phase);
            apb_reg_item item;
            vif.drv_cb.PSEL <= 0;
            vif.drv_cb.PENABLE <= 0;
            wait (vif.PRESETn === 1'b1);
            forever begin
                seq_item_port.get_next_item(item);
                @(vif.drv_cb);
                vif.drv_cb.PSEL <= 1;
                vif.drv_cb.PENABLE <= 0;
                vif.drv_cb.PWRITE <= item.write;
                vif.drv_cb.PADDR <= item.address;
                vif.drv_cb.PWDATA <= item.data;
                vif.drv_cb.PSTRB <= item.strobes;
                @(vif.drv_cb);
                vif.drv_cb.PENABLE <= 1;
                do @(vif.drv_cb); while (!vif.drv_cb.PREADY);
                vif.drv_cb.PSEL <= 0;
                vif.drv_cb.PENABLE <= 0;
                seq_item_port.item_done();
            end
        endtask
    endclass

    class apb_reg_monitor extends uvm_component;
        `uvm_component_utils(apb_reg_monitor)
        virtual apb_reg_if vif;
        uvm_analysis_port #(apb_reg_item) observed;
        covergroup operations;
            option.per_instance = 1;
            cp_write: coverpoint vif.PWRITE;
            cp_address: coverpoint vif.PADDR {
                bins control = {8'h00};
                bins status = {8'h04};
                bins unmapped = default;
            }
            cp_strobes: coverpoint vif.PSTRB { bins none = {0}; bins full = {15}; bins partial = default; }
            cp_error: coverpoint vif.PSLVERR;
            cross cp_write, cp_address;
        endgroup
        function new(string name, uvm_component parent);
            super.new(name, parent);
            observed = new("observed", this);
            operations = new();
        endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db#(virtual apb_reg_if)::get(this, "", "vif", vif))
                `uvm_fatal("NOVIF", "apb_reg_if was not configured")
        endfunction
        task run_phase(uvm_phase phase);
            apb_reg_item item;
            forever begin
                @(posedge vif.PCLK);
                #2ns;
                if (vif.PRESETn && vif.PSEL && vif.PENABLE && vif.PREADY) begin
                    item = apb_reg_item::type_id::create("observed_item");
                    item.write = vif.PWRITE;
                    item.address = vif.PADDR;
                    item.data = vif.PWDATA;
                    item.strobes = vif.PSTRB;
                    item.read_data = vif.PRDATA;
                    item.error = vif.PSLVERR;
                    operations.sample();
                    observed.write(item);
                end
            end
        endtask
    endclass

    class apb_reg_scoreboard extends uvm_subscriber #(apb_reg_item);
        `uvm_component_utils(apb_reg_scoreboard)
        bit [31:0] expected_control;
        int transaction_count;
        int error_count;
        function new(string name, uvm_component parent); super.new(name, parent); endfunction
        function void write(apb_reg_item item);
            bit expected_error = (item.address != 8'h00 && item.address != 8'h04) || (item.write && item.address == 8'h04);
            transaction_count++;
            if (item.error != expected_error) begin
                error_count++;
                `uvm_error("APB_SB", "PSLVERR mismatch")
            end
            if (item.write && item.address == 8'h00 && !item.error) begin
                for (int index = 0; index < 4; index++)
                    if (item.strobes[index]) expected_control[index*8 +: 8] = item.data[index*8 +: 8];
            end else if (!item.write && item.address == 8'h00 && item.read_data != expected_control) begin
                error_count++;
                `uvm_error("APB_SB", $sformatf("control read mismatch expected=%08x actual=%08x", expected_control, item.read_data))
            end else if (!item.write && item.address == 8'h04 && item.read_data != 32'hA5A5_5A5A) begin
                error_count++;
                `uvm_error("APB_SB", "status read mismatch")
            end
        endfunction
        function void check_phase(uvm_phase phase);
            if (transaction_count < 7) begin
                error_count++;
                `uvm_error("APB_SB", "not all directed APB transactions were observed")
            end
        endfunction
        function void report_phase(uvm_phase phase);
            if (error_count == 0) $display("APB_REG_SCOREBOARD_PASS transactions=%0d", transaction_count);
            else $display("TEST_FAILED APB_REG_SCOREBOARD errors=%0d", error_count);
        endfunction
    endclass

    class apb_reg_env extends uvm_env;
        `uvm_component_utils(apb_reg_env)
        uvm_sequencer #(apb_reg_item) sequencer;
        apb_reg_driver driver;
        apb_reg_monitor monitor;
        apb_reg_scoreboard scoreboard;
        function new(string name, uvm_component parent); super.new(name, parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            sequencer = uvm_sequencer#(apb_reg_item)::type_id::create("sequencer", this);
            driver = apb_reg_driver::type_id::create("driver", this);
            monitor = apb_reg_monitor::type_id::create("monitor", this);
            scoreboard = apb_reg_scoreboard::type_id::create("scoreboard", this);
        endfunction
        function void connect_phase(uvm_phase phase);
            driver.seq_item_port.connect(sequencer.seq_item_export);
            monitor.observed.connect(scoreboard.analysis_export);
        endfunction
    endclass

    class apb_reg_test extends uvm_test;
        `uvm_component_utils(apb_reg_test)
        apb_reg_env env;
        function new(string name, uvm_component parent); super.new(name, parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            env = apb_reg_env::type_id::create("env", this);
        endfunction
        task run_phase(uvm_phase phase);
            apb_reg_sequence seq;
            phase.raise_objection(this);
            seq = apb_reg_sequence::type_id::create("sequence");
            seq.start(env.sequencer);
            repeat (5) @(env.monitor.vif.mon_cb);
            phase.drop_objection(this);
        endtask
    endclass
endpackage
