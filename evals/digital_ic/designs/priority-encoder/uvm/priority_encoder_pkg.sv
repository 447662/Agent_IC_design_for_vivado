package priority_encoder_pkg;
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    class priority_item extends uvm_sequence_item;
        rand bit [7:0] req;
        bit [2:0] index;
        bit valid;
        `uvm_object_utils_begin(priority_item)
            `uvm_field_int(req, UVM_DEFAULT)
            `uvm_field_int(index, UVM_DEFAULT | UVM_NOCOMPARE)
            `uvm_field_int(valid, UVM_DEFAULT | UVM_NOCOMPARE)
        `uvm_object_utils_end
        function new(string name = "priority_item"); super.new(name); endfunction
    endclass

    class priority_sequence extends uvm_sequence #(priority_item);
        `uvm_object_utils(priority_sequence)
        function new(string name = "priority_sequence"); super.new(name); endfunction
        task send(bit [7:0] value);
            priority_item item = priority_item::type_id::create("item");
            start_item(item);
            item.req = value;
            finish_item(item);
        endtask
        task body();
            send(8'h00);
            for (int index = 0; index < 8; index++) send(8'(1 << index));
            send(8'b1000_0001);
            send(8'b0101_1010);
            repeat (48) begin
                priority_item item = priority_item::type_id::create("random_item");
                start_item(item);
                assert(item.randomize());
                finish_item(item);
            end
        endtask
    endclass

    class priority_driver extends uvm_driver #(priority_item);
        `uvm_component_utils(priority_driver)
        virtual priority_encoder_if vif;
        function new(string name, uvm_component parent); super.new(name, parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db#(virtual priority_encoder_if)::get(this, "", "vif", vif))
                `uvm_fatal("NOVIF", "priority_encoder_if was not configured")
        endfunction
        task run_phase(uvm_phase phase);
            priority_item item;
            vif.drv_cb.req <= '0;
            forever begin
                seq_item_port.get_next_item(item);
                @(vif.drv_cb);
                vif.drv_cb.req <= item.req;
                seq_item_port.item_done();
            end
        endtask
    endclass

    class priority_monitor extends uvm_component;
        `uvm_component_utils(priority_monitor)
        virtual priority_encoder_if vif;
        uvm_analysis_port #(priority_item) observed;
        covergroup patterns;
            option.per_instance = 1;
            cp_valid: coverpoint vif.mon_cb.valid;
            cp_index: coverpoint vif.mon_cb.index iff (vif.mon_cb.valid) { bins all_indices[] = {[0:7]}; }
            cp_request_count: coverpoint $countones(vif.mon_cb.req) {
                bins idle = {0}; bins onehot = {1}; bins multiple = {[2:8]};
            }
            cross cp_valid, cp_request_count;
        endgroup
        function new(string name, uvm_component parent);
            super.new(name, parent);
            observed = new("observed", this);
            patterns = new();
        endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db#(virtual priority_encoder_if)::get(this, "", "vif", vif))
                `uvm_fatal("NOVIF", "priority_encoder_if was not configured")
        endfunction
        task run_phase(uvm_phase phase);
            priority_item item;
            forever begin
                @(vif.mon_cb);
                item = priority_item::type_id::create("observed_item");
                item.req = vif.mon_cb.req;
                item.index = vif.mon_cb.index;
                item.valid = vif.mon_cb.valid;
                patterns.sample();
                observed.write(item);
            end
        endtask
    endclass

    class priority_scoreboard extends uvm_subscriber #(priority_item);
        `uvm_component_utils(priority_scoreboard)
        int checked;
        int error_count;
        function new(string name, uvm_component parent); super.new(name, parent); endfunction
        function void write(priority_item item);
            bit expected_valid = |item.req;
            bit [2:0] expected_index = '0;
            for (int index = 0; index < 8; index++)
                if (item.req[index]) expected_index = 3'(index);
            checked++;
            if (item.valid != expected_valid || (expected_valid && item.index != expected_index)) begin
                error_count++;
                `uvm_error("PRIORITY_SB", $sformatf("req=%02x expected valid/index=%0d/%0d actual=%0d/%0d", item.req, expected_valid, expected_index, item.valid, item.index))
            end
        endfunction
        function void check_phase(uvm_phase phase);
            if (checked < 50) begin
                error_count++;
                `uvm_error("PRIORITY_SB", "insufficient observed transactions")
            end
        endfunction
        function void report_phase(uvm_phase phase);
            if (error_count == 0) $display("PRIORITY_ENCODER_SCOREBOARD_PASS checked=%0d", checked);
            else $display("TEST_FAILED PRIORITY_ENCODER_SCOREBOARD errors=%0d", error_count);
        endfunction
    endclass

    class priority_env extends uvm_env;
        `uvm_component_utils(priority_env)
        uvm_sequencer #(priority_item) sequencer;
        priority_driver driver;
        priority_monitor monitor;
        priority_scoreboard scoreboard;
        function new(string name, uvm_component parent); super.new(name, parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            sequencer = uvm_sequencer#(priority_item)::type_id::create("sequencer", this);
            driver = priority_driver::type_id::create("driver", this);
            monitor = priority_monitor::type_id::create("monitor", this);
            scoreboard = priority_scoreboard::type_id::create("scoreboard", this);
        endfunction
        function void connect_phase(uvm_phase phase);
            driver.seq_item_port.connect(sequencer.seq_item_export);
            monitor.observed.connect(scoreboard.analysis_export);
        endfunction
    endclass

    class priority_test extends uvm_test;
        `uvm_component_utils(priority_test)
        priority_env env;
        function new(string name, uvm_component parent); super.new(name, parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            env = priority_env::type_id::create("env", this);
        endfunction
        task run_phase(uvm_phase phase);
            priority_sequence seq;
            phase.raise_objection(this);
            seq = priority_sequence::type_id::create("sequence");
            seq.start(env.sequencer);
            repeat (5) @(env.monitor.vif.mon_cb);
            phase.drop_objection(this);
        endtask
    endclass
endpackage
