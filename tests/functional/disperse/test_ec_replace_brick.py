"""
 Copyright (C) 2020 Red Hat, Inc. <http://www.redhat.com>

 This program is free software; you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 2 of the License, or
 any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License along
 with this program; if not, write to the Free Software Foundation, Inc.,
 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

 Description:
    TC to test replace brick on EC volume
"""

# disruptive;disp,dist-disp
import traceback
from random import choice
from tests.d_parent_test import DParentTest


class TestEcBrickReplace(DParentTest):

    def terminate(self):
        """
        Complete memory logging proc, IO on mountpoint and fd IO, if the TC
        fails midway
        """
        try:
            if self.io_mem_monitor_running:
                for proc in self.cmd_list_procs:
                    self.redant.wait_till_async_command_ends(proc)

            for server in self.server_list:
                cmd = f"rm -f {self.log_file_mem_monitor}"
                self.redant.execute_abstract_op_node(cmd, server, False)

            _io_rc = False
            if self.is_io_running:
                if not (self.redant.wait_for_io_to_complete(
                        self.all_mounts_procs, self.mounts)):
                    _io_rc = True

            _fd_rc = False
            if self.is_fd_io_running:
                if not (self.redant.wait_for_io_to_complete(
                        self.all_fd_procs, self.mounts)):
                    _fd_rc = True

            if _io_rc:
                raise Exception("Failed to wait for IO to complete")

            if _fd_rc:
                raise Exception("Failed to wait for FD IO to complete")

        except Exception as error:
            tb = traceback.format_exc()
            self.redant.logger.error(error)
            self.redant.logger.error(tb)
        super().terminate()

    def run_test(self, redant):
        """
        - Start resource consumption tool
        - Create directory dir1
        - Create 5 directory and 5 files in dir of mountpoint
        - Rename all files inside dir1 at mountpoint
        - Create softlink and hardlink of files in dir1 of mountpoint
        - Delete op for deleting all file in one of the dirs inside dir1
        - Change chmod, chown, chgrp
        - Create tiny, small, medium and large file
        - Get arequal before replacing brick
        - Replace brick
        - Get arequal after replacing brick
        - Compare Arequal's
        - Create IO's
        - Replace brick while IO's are going on
        - Validating IO's and waiting for it to complete
        """
        self.is_io_running = False
        self.io_mem_monitor_running = False
        self.is_fd_io_running = False
        self.mounts = redant.es.get_mnt_pts_dict_in_list(self.vol_name)

        # Starting resource consumption using top
        self.log_file_mem_monitor = '/var/log/glusterfs/mem_usage.log'
        cmd = ("for i in {1..20};do top -n 1 -b|egrep 'RES|gluster' & free -h"
               f" 2>&1 >> {self.log_file_mem_monitor} ; sleep 10;done")

        self.cmd_list_procs = []
        for server in self.server_list:
            proc = redant.execute_command_async(cmd, server)
            self.cmd_list_procs.append(proc)
        self.io_mem_monitor_running = True

        # Creating dir1
        redant.create_dir(self.mountpoint, "dir1", self.client_list[0])

        # Create 5 dir and 5 files in each dir at mountpoint on dir1
        start, end = 1, 5
        for mount_obj in self.mounts:
            # Number of dir and files to be created.
            dir_range = ("%s..%s" % (str(start), str(end)))
            file_range = ("%s..%s" % (str(start), str(end)))
            # Create dir 1-5 at mountpoint.
            redant.create_dir(mount_obj['mountpath'], "dir1/dir{%s}"
                              % dir_range, mount_obj['client'])

            # Create files inside each dir.
            cmd = ('touch %s/dir1/dir{%s}/file{%s};'
                   % (mount_obj['mountpath'], dir_range, file_range))
            redant.execute_abstract_op_node(cmd, mount_obj['client'])

            # Increment counter so that at next client dir and files are made
            # with diff offset. Like at next client dir will be named
            # dir6, dir7...dir10. Same with files.
            start += 5
            end += 5

        # Rename all files inside dir1 at mountpoint on dir1
        cmd = (f"cd {self.mountpoint}/dir1/dir1/; "
               "for FILENAME in *; do mv $FILENAME Unix_$FILENAME; done;")
        redant.execute_abstract_op_node(cmd, self.client_list[0])

        # Truncate at any dir in mountpoint inside dir1
        # start is an offset to be added to dirname to act on
        # diff files at diff clients.
        start = 1
        for mount_obj in self.mounts:
            cmd = (f"cd {mount_obj['mountpath']}/dir1/dir{start}/; "
                   "for FILENAME in *; do echo > $FILENAME; done;")
            redant.execute_abstract_op_node(cmd, mount_obj['client'])

        # Create softlink and hardlink of files in mountpoint. Start is an
        # offset to be added to dirname to act on diff files at diff clients.
        start = 1
        for mount_obj in self.mounts:
            cmd = (f"cd {mount_obj['mountpath']}/dir1/dir{start}; "
                   "for FILENAME in *; do ln -s $FILENAME softlink_$FILENAME;"
                   "done;")
            redant.execute_abstract_op_node(cmd, mount_obj['client'])

            cmd = (f"cd {mount_obj['mountpath']}/dir1/dir{start + 1}; "
                   "for FILENAME in *; do ln $FILENAME hardlink_$FILENAME;"
                   "done;")
            redant.execute_abstract_op_node(cmd, mount_obj['client'])
            start += 5

        # chmod, chown, chgrp inside dir1
        # start and end used as offset to access diff files
        # at diff clients.
        start, end = 2, 5
        for mount_obj in self.mounts:
            dir_file_range = '%s..%s' % (str(start), str(end))
            cmd = (f"chmod 777 {mount_obj['mountpath']}/dir1/dir"
                   "{%s}/file{%s}" % (dir_file_range, dir_file_range))
            redant.execute_abstract_op_node(cmd, mount_obj['client'])

            cmd = (f"chown root {mount_obj['mountpath']}/dir1/dir"
                   "{%s}/file{%s}" % (dir_file_range, dir_file_range))
            redant.execute_abstract_op_node(cmd, mount_obj['client'])

            cmd = (f"chgrp root {mount_obj['mountpath']}/dir1/dir"
                   "{%s}/file{%s}" % (dir_file_range, dir_file_range))
            redant.execute_abstract_op_node(cmd, mount_obj['client'])
            start += 5
            end += 5

        # Create tiny, small, medium and large file
        # at mountpoint. Offset to differ filenames
        # at diff clients.
        offset = 1
        for mount_obj in self.mounts:
            cmd = (f"fallocate -l 100 {mount_obj['mountpath']}/"
                   f"tiny_file{offset}.txt")
            redant.execute_abstract_op_node(cmd, mount_obj['client'])

            cmd = (f"fallocate -l 20M {mount_obj['mountpath']}/"
                   f"small_file{offset}.txt")
            redant.execute_abstract_op_node(cmd, mount_obj['client'])

            cmd = (f"fallocate -l 200M {mount_obj['mountpath']}/"
                   f"medium_file{offset}.txt")
            redant.execute_abstract_op_node(cmd, mount_obj['client'])

            cmd = (f"fallocate -l 1G {mount_obj['mountpath']}/"
                   f"large_file{offset}.txt")
            redant.execute_abstract_op_node(cmd, mount_obj['client'])
            offset += 1

        # Get arequal before replacing brick
        result_before_replacing_brick = \
            redant.collect_mounts_arequal(self.mounts[0])

        # Replacing a brick of random choice
        sbrick = choice(redant.get_all_bricks(self.vol_name,
                        self.server_list[0]))
        sbrick_host, sbrick_root = sbrick.split(':')
        dbrick_root = sbrick_root[0:sbrick.split(':')[1].rfind("/")]
        dbrick = f"{sbrick_host}:{dbrick_root}/new_replaced_brick"
        ret = redant.replace_brick_from_volume(self.vol_name,
                                               self.server_list[0],
                                               self.server_list,
                                               sbrick, dbrick)
        if not ret:
            raise Exception("Unexpected:Replace brick is not successful")

        # Wait for brick to come online
        bricks_list = redant.get_all_bricks(self.vol_name,
                                            self.server_list[0])
        ret = redant.wait_for_bricks_to_come_online(self.vol_name,
                                                    self.server_list,
                                                    bricks_list)
        if not ret:
            raise Exception("Unexpected: Bricks are not online")

        # Monitor heal completion
        if not redant.monitor_heal_completion(self.server_list[0],
                                              self.vol_name):
            raise Exception("Heal has not yet completed")

        # Check if bricks are online
        ret = redant.are_bricks_online(self.vol_name, bricks_list,
                                       self.server_list[0])
        if not ret:
            raise Exception("Unexpected:All bricks are not online")

        # Get areequal after replacing brick
        result_after_replacing_brick = \
            redant.collect_mounts_arequal(self.mounts[0])

        # Comparing arequals
        if result_before_replacing_brick != result_after_replacing_brick:
            raise Exception('Arequals are not equals before replacing '
                            'brick and after replacing brick')

        # Creating files on client side for dir1
        # Write IO
        self.mounts = redant.es.get_mnt_pts_dict_in_list(self.vol_name)
        self.all_mounts_procs = []
        count = 1
        for mount_obj in self.mounts:
            proc = redant.create_deep_dirs_with_files(mount_obj['mountpath'],
                                                      count, 2, 10, 5, 5,
                                                      mount_obj['client'])
            self.all_mounts_procs.append(proc)
            count = count + 10
        self.is_io_running = True

        # Replacing a brick while IO's are going on
        sbrick = choice(redant.get_all_bricks(self.vol_name,
                        self.server_list[0]))
        sbrick_host, sbrick_root = sbrick.split(':')
        dbrick_root = sbrick_root[0:sbrick.split(':')[1].rfind("/")]
        dbrick = f"{sbrick_host}:{dbrick_root}/new_replaced_brick_1"
        ret = redant.replace_brick_from_volume(self.vol_name,
                                               self.server_list[0],
                                               self.server_list,
                                               sbrick, dbrick)
        if not ret:
            raise Exception("Unexpected: Replace brick is not successful")

        # Wait for brick to come online
        bricks_list = redant.get_all_bricks(self.vol_name,
                                            self.server_list[0])
        ret = redant.wait_for_bricks_to_come_online(self.vol_name,
                                                    self.server_list,
                                                    bricks_list)
        if not ret:
            raise Exception("Unexpected: Bricks are not online")

        # Validating IO's and waiting to complete
        ret = redant.validate_io_procs(self.all_mounts_procs,
                                       self.mounts)
        if not ret:
            raise Exception("IO failed on some of the clients")
        self.is_io_running = False

        # Create 2 directories and start IO's which opens FD
        cmd = "mkdir -p %s/count{1..2}" % self.mountpoint
        redant.execute_abstract_op_node(cmd, self.client_list[0])

        self.all_fd_procs, count = [], 1
        for mount_obj in self.mounts:
            cmd = (f"cd {mount_obj['mountpath']}; "
                   "python3 /usr/share/redant/script/fd_writes.py -n 10 "
                   f"-t 120 -d 5 -c 16 --dir count{count}")
            proc = redant.execute_command_async(cmd, mount_obj['client'])
            self.all_fd_procs.append(proc)
            count += 1
        self.is_fd_io_running = True

        # Replacing a brick while open FD IO's are going on
        sbrick = choice(redant.get_all_bricks(self.vol_name,
                        self.server_list[0]))
        sbrick_host, sbrick_root = sbrick.split(':')
        dbrick_root = sbrick_root[0:sbrick.split(':')[1].rfind("/")]
        dbrick = f"{sbrick_host}:{dbrick_root}/new_replaced_brick_2"
        ret = redant.replace_brick_from_volume(self.vol_name,
                                               self.server_list[0],
                                               self.server_list,
                                               sbrick, dbrick)
        if not ret:
            raise Exception("Unexpected: Replace brick is not successful")

        # Wait for brick to come online
        bricks_list = redant.get_all_bricks(self.vol_name,
                                            self.server_list[0])
        ret = redant.wait_for_bricks_to_come_online(self.vol_name,
                                                    self.server_list,
                                                    bricks_list)
        if not ret:
            raise Exception("Unexpected: Bricks are not online")

        # Validating IO's and waiting to complete
        ret = redant.validate_io_procs(self.all_fd_procs,
                                       self.mounts)
        if not ret:
            raise Exception("IO failed on some of the clients")
        self.is_fd_io_running = False

        # Close connection and check file exist for memory log
        ret = redant.path_exists(self.server_list[0],
                                 self.log_file_mem_monitor)
        if not ret:
            raise Exception("Unexpected:Memory log file does not exist")

        for proc in self.cmd_list_procs:
            ret = redant.wait_till_async_command_ends(proc)
            if ret['error_code'] != 0:
                raise Exception("Memory logging failed")
        self.io_mem_monitor_running = False
