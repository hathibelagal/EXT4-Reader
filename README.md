# ext4 Reader
This is a very rudimentary command-line tool that can read ext4 file systems. You can either point it to a `/dev/sdXX` file, or a file you created using the `mke2fs` command.

It does support flexible block groups.

Note: I am working on this tool primarily to recover data from a filesystem that was spoiled by a failed GParted partition-resizing operation.

### Usage

This tool expects the path of the file system, along with its size (in bytes).

```
./reader.py -f <filesystem> -s <size>
```

I've tested it only on Ubuntu 14.04.
