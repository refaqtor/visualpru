from __future__ import print_function
from __future__ import division

import os
import mmap
import struct
import re

import pasm

class PRU:

    def __init__(self, id, constants, shared_constants):
        self.id = id
        self.constants = constants
        self.shared_constants = shared_constants
        self.f = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        self.pruss_mmap = self.map_memory(self.f, self.shared_constants.PRUSS_RANGE)

        self.source_files = []
        self.compiled_file = {}
        self.errors = []
        self.warnings = []

        self.memory_range = {'dram':{'offset':0,'address_count':0},'shared':{'offset':0,'address_count':0},'ddr':{'offset':0,'address_count':0}}

    #Pass in the range of addresses we want to cover, and size the mmap accordingly
    def map_memory(self,f, memory_range):
        if (memory_range[1] - memory_range[0] + 1) % mmap.PAGESIZE == 0:
            #The range is fully covered by a multiple of the pagesize
            multiple = (memory_range[1] - memory_range[0] + 1) // mmap.PAGESIZE
        else:
            #Since the page size is not evenly divisible by the range, we need to round up to the next page size to fully cover the entire range
            multiple = 1 + ((memory_range[1] - memory_range[0] + 1) // mmap.PAGESIZE)

        mm = mmap.mmap(f, mmap.PAGESIZE * multiple, offset=memory_range[0])

        return mm

    def unmap_memory(self):
        self.pruss_mmap.close()
        os.close(self.f)

    def read_register(self,register_offset,byte_count):
        r = self.pruss_mmap[register_offset:register_offset+byte_count]
        return struct.unpack("<L",r)[0]

    def write_register(self,register_offset,byte_count,value):
        packed_value = struct.pack("<L",value)
        self.pruss_mmap[register_offset:register_offset+byte_count] = packed_value

    def is_running(self):
        r = self.read_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.CONTROL_REGISTER_OFFSET,4)
        if (r & (1<<self.shared_constants.RUNSTATE_BIT)) == 0:
            return False
        else:
            return True

    def reset(self,value=None):
        r = self.read_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.CONTROL_REGISTER_OFFSET,4)
        #Clear bit to trigger a reset
        r &= ~(1<<self.shared_constants.SOFT_RST_N_BIT)

        #Set a start instruction if specified, otherwise just jump to the default
        if value is not None:
            #Clear the current counter value and set the new one
            r &= ~(0xFFFF<<self.shared_constants.PCOUNTER_RST_VAL_BIT)
            r |= ((value & 0xFFFF)<<self.shared_constants.PCOUNTER_RST_VAL_BIT)

        self.write_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.CONTROL_REGISTER_OFFSET,4,r)

    def set_singlestep_mode(self):
        r = self.read_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.CONTROL_REGISTER_OFFSET,4)
        r |= (1<<self.shared_constants.SINGLE_STEP_BIT)
        self.write_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.CONTROL_REGISTER_OFFSET,4,r)

    def set_freerunning_mode(self):
        r = self.read_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.CONTROL_REGISTER_OFFSET,4)
        r &= ~(1<<self.shared_constants.SINGLE_STEP_BIT)
        self.write_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.CONTROL_REGISTER_OFFSET,4,r)

    def get_run_mode(self):
        r = self.read_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.CONTROL_REGISTER_OFFSET,4)
        if r&(1<<self.shared_constants.SINGLE_STEP_BIT) != 0:
            mode = 'step'
        else:
            mode = 'continuous'
        return mode

    #TODO: Also check to see if the PRU is asleep
    def get_status(self):
        if self.is_running():
            status = 'running'
        else:
            status = 'halted'
        return status

    def get_program_counter_value(self):
        r = self.read_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.STATUS_REGISTER_OFFSET,4)
        return r & 0xFFFF

    def halt(self):
        r = self.read_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.CONTROL_REGISTER_OFFSET,4)
        r &= ~(1<<self.shared_constants.ENABLE_BIT)
        self.write_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.CONTROL_REGISTER_OFFSET,4,r)

    def run(self):
        r = self.read_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.CONTROL_REGISTER_OFFSET,4)
        r |= (1<<self.shared_constants.ENABLE_BIT)
        self.write_register(self.constants.CONTROL_BLOCK_OFFSET+self.shared_constants.CONTROL_REGISTER_OFFSET,4,r)

    def write_opcodes_to_iram(self,opcodes):
        for i,opcode in enumerate(opcodes):
            address = self.constants.IRAM_RANGE[0]+i*4
            if address >= self.constants.IRAM_RANGE[0] and address <= self.constants.IRAM_RANGE[1]:
                self.write_register(address,4,opcode)

    def get_gpreg_register(self,offset):
        return self.read_register(self.constants.DEBUG_BLOCK_OFFSET+self.shared_constants.GPREG_BLOCK_OFFSET+offset*4,4)

    def get_gpreg_registers(self):
        registers = []
        for i in range(self.shared_constants.GPREG_COUNT):
            registers.append({'name' : 'r'+str(i), 'value': self.get_gpreg_register(i)})
        return registers

    #TODO: Ensure tahat requested addresses are within the memory range
    def get_dram_block(self):
        registers = []
        for i in range(self.memory_range['dram']['address_count']):
            address = self.constants.DRAM_RANGE[0]+self.memory_range['dram']['offset']+i*4
            if address >= self.constants.DRAM_RANGE[0] and address <= self.constants.DRAM_RANGE[1]:
                registers.append({'name' : hex(address), 'value': self.read_register(address,4)})
        return registers

    def get_shareddram_block(self):
        registers = []
        for i in range(self.memory_range['shared']['address_count']):
            address = self.shared_constants.SHAREDDRAM_RANGE[0]+self.memory_range['shared']['offset']+i*4
            if address >= self.shared_constants.SHAREDDRAM_RANGE[0] and address <= self.shared_constants.SHAREDDRAM_RANGE[1]:
                registers.append({'name' : hex(address), 'value': self.read_register(address,4)})
        return registers

    def compile_and_upload_program(self, compilation_directory, source_files):

        #Create the PRU directory structure if it doesn't exist
        program_directory = os.path.join(compilation_directory,self.id)
        if not os.path.exists(program_directory):
            os.makedirs(program_directory)

        #Create the source files and store an internal copy
        for source_file in source_files:
            with open(os.path.join(program_directory,source_file['name']),'w') as f:
                f.write(source_file['content'])

        self.source_files = source_files

        #Get the primary filename, which is the first file in the array by convention
        #TODO: Make it an entry in the object? eg. check for a 'primary':true flag
        primary_filename = source_files[0]['name']

        #Compile the source files
        errors, warnings = pasm.compile(program_directory,primary_filename)

        self.errors = errors
        self.warnings = warnings

        #Write to PRU memory if there are no errors
        if not errors:
            #A source file is guaranteed to have a '.p' or '.hp' extension, so we can rely string substitution
            compiled_filename = re.sub('(?:\.p)$|(?:\.hp)$','.lst',primary_filename)

            #Write the program to memory
            #TODO: Confirm that the combined size of the opcodes is than the PRU's IRAM...
            #    : len(opcodes) * 4 <= self.shared_constants.MAX_IRAM_SIZE where 4 represents the bytesize of each opcode
            opcodes, instructions = pasm.parse_compiler_output(program_directory,compiled_filename)
            self.write_opcodes_to_iram(opcodes)
            self.compiled_file = {'name':compiled_filename,'content':instructions}

    def set_memory_range(self,type,offset,address_count):
        self.memory_range[type] = {'offset':offset, 'address_count':address_count}
        print(self.memory_range)

    #NOTE: This function returns a dictionary oject with state information in a format that mirrors the front-end model state
    def get_state(self):
        pru = {}

        pru['id'] = self.id
        pru['state'] = {'programCounter':self.get_program_counter_value(), 'status': self.get_status(), 'runMode': self.get_run_mode()}
        pru['program'] = {
                            'sourceFiles' : self.source_files,
                            'compiledFile' : self.compiled_file,
                            'errors' : self.errors,
                            'warnings' : self.warnings
                         }

        pru['memory'] = {'generalPurpose':self.get_gpreg_registers(), 'dram': self.get_dram_block(), 'shared': self.get_shareddram_block()}

        return pru