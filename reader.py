#!/usr/bin/python
#
# Copyright (C) 2017 Hathibelagal
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import struct
from getopt import getopt
import sys


class Ext4FileSystemReader:
    
    def __init__(self, args):
        self.file_system = False
        self.file_system_size = False
        self.recover_files = False

        opts, _ = getopt(args, 'f:s:r:')
        for option, value in opts:
            if option == '-f':
                self.file_system = value
                print("Using %s as the file system" % self.file_system)
            if option == '-s':
                self.file_system_size = long(value)
                print("Using %d as the size of the file system" % self.file_system_size)
            if option == '-r':
                if value == 'yes':
                    self.recover_files = True

        if self.file_system and self.file_system_size:
            self.read_first_block()
        else:
            print("Usage: -f <filesystem> -s <filesystem_size> -r <yes|no>")
            print("Note: Superuser privileges might be required")
            exit(1)
                        
    def read_first_block(self):
        with open(self.file_system) as f:

            # Skip padding
            f.read(1024)
            super_block = f.read(1024)
            inode_details = struct.unpack('13I',super_block[0:13 * 4])
            diagnostic_details = struct.unpack('6H',super_block[52:52+6*2])

            print("File system details:")
            self.n_inodes = inode_details[0]
            self.n_blocks = inode_details[1]
            self.block_size = 2 ** (10 + inode_details[6])
            self.blocks_per_group = inode_details[8]
            self.block_group_size = self.block_size * self.blocks_per_group
            self.inodes_per_group = inode_details[10]
            self.number_of_block_groups = self.file_system_size / self.block_group_size + 1
            print("  Number of inodes: %d" % self.n_inodes)
            print("  Number of blocks: %d" % self.n_blocks)
            print("  Size of each block: %d bytes" % self.block_size)
            print("  Size of block group: %d bytes" % self.block_group_size)
            print("  Number of blocks per group: %d" % self.blocks_per_group)
            print("  Number of inodes per group: %d" % self.inodes_per_group)
            print("  Number of block groups: %d" % self.number_of_block_groups)
            if inode_details[7] != 0:
                print("  Bigalloc is enabled. Cluster size is %d" % (2 ** inode_details[7]))
            print("  Signature: %x" % diagnostic_details[2])

            status = "Good"
            if diagnostic_details[3] != 0x0001:
                status = "Errors found"
            print("  Status: %s" % status)

            os_details = struct.unpack('I',super_block[68:68 + 1 * 4])
            os_name = "Unknown"
            if os_details[0] == 0:
                os_name = "Linux"
            elif os_details[0] == 3:
                os_name = "FreeBSD"            
            print("  Operating system: %s" % os_name)

            first_inode = struct.unpack('IH',super_block[0x54:0x54 + 1*4 + 1*2])
            print("  First non-reserved inode at: %d" % first_inode[0])
            self.first_usable_inode = first_inode[0]
            self.inode_size = first_inode[1]
            print("  Size of inode: %d bytes" % first_inode[1])

            incompat_details = struct.unpack('3I',super_block[0x5C:0x5C + 3 * 4])
            if incompat_details[0] & 0x10:
                print("  Has reserved blocks for expansion: True")
                self.reserved_blocks = True
            if incompat_details[1] & 0x80 == 0:
                self.group_descriptor_size = 32
                print("  Size of block group descriptor: 32 bytes")
            else:
                print("  Size of block group descriptor: >32 bytes")
                print("  ERROR: This block group descriptor size is not supported.")
                exit(1)
            if incompat_details[1] & 0x200:
                self.flex = True
                self.flex_size = 2 ** struct.unpack('b',super_block[0x174])[0]
                print("  This FS has flexible block groups of size %d" % self.flex_size)
            if incompat_details[2] & 0x1:
                print("  Sparse super blocks: True")
                self.sparse_super_blocks = True            

            #Skip rest of the block
            f.read(2048)

            #Read group descriptors
            for i in xrange(self.number_of_block_groups):
                group_descriptor = struct.unpack('3I4HI4H', f.read(self.group_descriptor_size))
                print("  Inode table found at %d for block group %d" % (group_descriptor[2], i))

            print("----------------------------------------------------")
            

    def has_super_block(self, n):
        valid_values = [0]
        for i in xrange(1,33):
            valid_values.append(3 ** i)
            valid_values.append(5 ** i)
            valid_values.append(7 ** i)
        return n in valid_values

    def seek_inode_table_details(self):
        with open(self.file_system, "rb") as f:
            for i in xrange(0, self.number_of_block_groups):
                if self.has_super_block(i):
                    block_group_location = self.block_group_size * i
                    print("Looking at location: %d" % block_group_location)
                    f.seek(block_group_location + self.block_size, 0)
                    self.inode_tables = []
                    for i in xrange(self.number_of_block_groups):
                        current_group_descriptor = struct.unpack('3I4HI4H', f.read(self.group_descriptor_size))
                        current_inode_table_details = {}
                        current_inode_table_details['number'] = i
                        current_inode_table_details['location'] = current_group_descriptor[2]
                        current_inode_table_details['flags'] = current_group_descriptor[6]
                        current_inode_table_details['free_inodes'] = current_group_descriptor[4]
                        current_inode_table_details['directories'] = current_group_descriptor[5]
                        self.inode_tables.append(current_inode_table_details)

    def read_all_inodes(self):
        block_group_number = 0
        inode_number = 1
        with open(self.file_system, "rb") as f:
            for block_group_number in xrange(self.number_of_block_groups):

                #Read only initialized inode tables
                if self.inode_tables[block_group_number]['flags'] != 4:
                    print("Inode table uninitialized in block group %d" % block_group_number)
                    continue

                print("Reading inode table of block group %d"%(block_group_number))
                starting_position = self.inode_tables[block_group_number]['location']
                f.seek(starting_position * self.block_size)
                for q in xrange(self.inodes_per_group):
                    current_inode = f.read(self.inode_size)
                    current_inode_meta_data = struct.unpack('2H5I', current_inode[:2 * 2 + 5 * 4])
                    current_file_size = current_inode_meta_data[2]
                    current_file_type = "Other"
                    if current_inode_meta_data[0] & 0x4000:
                        current_file_type = "Directory"
                    elif current_inode_meta_data[0] & 0x8000:
                        current_file_type = "Regular file"
                    number_of_512_blocks = struct.unpack('I', current_inode[0x1C: 0x1C + 1 * 4])[0]
                    uses_extents = (struct.unpack('I', current_inode[0x20: 0x20 + 1 * 4])[0] & 0x80000) != 0
                    if current_file_size > 0:
                        print("%d -> (Permissions: %x, Size: %d, Type: %s, sBlocks: %d, Extents: %s)" % (inode_number, 
                                        current_inode_meta_data[0], 
                                        current_inode_meta_data[2], 
                                        current_file_type, 
                                        number_of_512_blocks, 
                                        uses_extents))
                        if (self.recover_files and 
                                    current_file_type == 'Regular file' and 
                                    inode_number >= self.first_usable_inode):
                            self.recover(current_inode, current_file_type, uses_extents, 
                                         number_of_512_blocks, current_file_size) 
                    inode_number += 1

    def recover(self, inode, file_type, uses_extents, number_of_512_blocks, current_file_size):
        i_block = inode[0x28:0x28 + 60]
        if uses_extents:
            extent_header = struct.unpack('4HI', i_block[:12])
            if extent_header[0] != 0xF30A:
                print("Error in extent header: %x" % extent_header[0])
                return
            else:
                n_entries = extent_header[1]
                depth = extent_header[3]
                if depth == 0 and n_entries > 0:
                    self.recover_from_leaf_node(i_block, number_of_512_blocks, 
                                                current_file_size, n_entries)

    def recover_from_leaf_node(self, i_block, number_of_512_blocks, current_file_size, n_entries):
        with open(self.file_system, "rb") as f:
            starting_point = 12
            total_bytes_remaining = current_file_size
            for entry in xrange(n_entries):
                leaf = struct.unpack('I2HI',i_block[starting_point:starting_point+12])
                block_number_lo = leaf[3]
                block_number_hi = leaf[2]
                block_number = block_number_hi << 32 | block_number_lo
                maximum_readable_bytes = leaf[1] * self.block_size
                if block_number < self.n_blocks:
                    print("Fetching block: %d" % block_number)
                    f.seek(block_number * self.block_size)
                    total_bytes_read = 0
                    for i in xrange(number_of_512_blocks):
                        bytes_to_read = 512
                        if bytes_to_read > total_bytes_remaining:
                            bytes_to_read = total_bytes_remaining
                        print("DATA (%d, %d)\n-------------" % (entry, i))
                        print(f.read(bytes_to_read))
                        total_bytes_remaining -= bytes_to_read
                        total_bytes_read += bytes_to_read
                        if total_bytes_remaining <= 0:
                            break
                        if total_bytes_read >= maximum_readable_bytes:
                            break
                else:
                    print("Bad block number found: %d" % block_number)
                starting_point+=12

if __name__ == "__main__":
    fs = Ext4FileSystemReader(sys.argv[1:])
    fs.seek_inode_table_details()
    fs.read_all_inodes()
