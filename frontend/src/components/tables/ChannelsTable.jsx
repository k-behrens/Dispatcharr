import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { MantineReactTable, useMantineReactTable } from 'mantine-react-table';
import useChannelsStore from '../../store/channels';
import { notifications } from '@mantine/notifications';
import API from '../../api';
import ChannelForm from '../forms/Channel';
import RecordingForm from '../forms/Recording';
import { TableHelper } from '../../helpers';
import { getDescendantProp } from '../../utils';
import logo from '../../images/logo.png';
import useVideoStore from '../../store/useVideoStore';
import useSettingsStore from '../../store/settings';
import usePlaylistsStore from '../../store/playlists';
import {
  Tv2,
  ScreenShare,
  Scroll,
  SquareMinus,
  CirclePlay,
  SquarePen,
  Binary,
  ArrowDown01,
  SquarePlus,
  Copy,
  CircleCheck,
  ScanEye,
  EllipsisVertical,
  CircleEllipsis,
  CopyMinus,
} from 'lucide-react';
import ghostImage from '../../images/ghost.svg';
import {
  Box,
  TextInput,
  Popover,
  ActionIcon,
  Select,
  Button,
  Paper,
  Flex,
  Text,
  Tooltip,
  Grid,
  Group,
  useMantineTheme,
  Center,
  Container,
  Switch,
  Menu,
  MultiSelect,
} from '@mantine/core';

const ChannelStreams = ({ channel, isExpanded }) => {
  const channelStreams = useChannelsStore(
    (state) => state.channels[channel.id]?.streams
  );
  const { playlists } = usePlaylistsStore();

  const removeStream = async (stream) => {
    const newStreamList = channelStreams.filter((s) => s.id !== stream.id);
    await API.updateChannel({
      ...channel,
      stream_ids: newStreamList.map((s) => s.id),
    });
  };

  const channelStreamsTable = useMantineReactTable({
    ...TableHelper.defaultProperties,
    data: channelStreams,
    columns: useMemo(
      () => [
        {
          size: 400,
          header: 'Name',
          accessorKey: 'name',
          Cell: ({ cell }) => (
            <div
              style={{
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {cell.getValue()}
            </div>
          ),
        },
        {
          size: 100,
          header: 'M3U',
          accessorFn: (row) =>
            playlists.find((playlist) => playlist.id === row.m3u_account)?.name,
          Cell: ({ cell }) => (
            <div
              style={{
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {cell.getValue()}
            </div>
          ),
        },
      ],
      [playlists]
    ),
    displayColumnDefOptions: {
      'mrt-row-actions': {
        size: 10,
      },
    },
    enableKeyboardShortcuts: false,
    enableColumnFilters: false,
    enableBottomToolbar: false,
    enableTopToolbar: false,
    enableTableHead: false,
    columnFilterDisplayMode: 'popover',
    enablePagination: false,
    enableRowVirtualization: true,
    enableColumnHeaders: false,
    rowVirtualizerOptions: { overscan: 5 }, //optionally customize the row virtualizer
    initialState: {
      density: 'compact',
    },
    enableRowActions: true,
    enableRowOrdering: true,
    mantineTableHeadRowProps: {
      style: { display: 'none' },
    },
    mantineTableBodyCellProps: {
      style: {
        // py: 0,
        padding: 4,
        borderColor: '#444',
        color: '#E0E0E0',
        fontSize: '0.85rem',
      },
    },
    mantineRowDragHandleProps: ({ table }) => ({
      onDragEnd: async () => {
        const { draggingRow, hoveredRow } = table.getState();

        if (hoveredRow && draggingRow) {
          channelStreams.splice(
            hoveredRow.index,
            0,
            channelStreams.splice(draggingRow.index, 1)[0]
          );

          const { streams: _, ...channelUpdate } = channel;

          API.updateChannel({
            ...channelUpdate,
            stream_ids: channelStreams.map((stream) => stream.id),
          });
        }
      },
    }),
    renderRowActions: ({ row }) => (
      <Tooltip label="Remove stream">
        <ActionIcon
          size="sm"
          color="red.9"
          variant="transparent"
          onClick={() => removeStream(row.original)}
        >
          <SquareMinus size="18" fontSize="small" />
        </ActionIcon>
      </Tooltip>
    ),
  });

  if (!isExpanded) {
    return <></>;
  }

  return (
    <Box style={{ width: '100%' }}>
      <MantineReactTable table={channelStreamsTable} />
    </Box>
  );
};

const m3uUrlBase = `${window.location.protocol}//${window.location.host}/output/m3u`;
const epgUrlBase = `${window.location.protocol}//${window.location.host}/output/epg`;
const hdhrUrlBase = `${window.location.protocol}//${window.location.host}/hdhr`;

const CreateProfilePopover = ({}) => {
  const [opened, setOpened] = useState(false);
  const [name, setName] = useState('');
  const theme = useMantineTheme();

  const setOpen = () => {
    setName('');
    setOpened(!opened);
  };

  const submit = async () => {
    await API.addChannelProfile({ name });
    setName('');
    setOpened(false);
  };

  return (
    <Popover
      opened={opened}
      onChange={setOpen}
      position="bottom"
      withArrow
      shadow="md"
    >
      <Popover.Target>
        <ActionIcon
          variant="transparent"
          color={theme.tailwind.green[5]}
          onClick={setOpen}
        >
          <SquarePlus />
        </ActionIcon>
      </Popover.Target>

      <Popover.Dropdown>
        <Group>
          <TextInput
            placeholder="Profile Name"
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
            size="xs"
          />

          <ActionIcon
            variant="transparent"
            color={theme.tailwind.green[5]}
            size="sm"
            onClick={submit}
          >
            <CircleCheck />
          </ActionIcon>
        </Group>
      </Popover.Dropdown>
    </Popover>
  );
};

const ChannelsTable = ({}) => {
  const {
    channels,
    isLoading: channelsLoading,
    fetchChannels,
    setChannelsPageSelection,
    profiles,
    selectedProfileId,
    setSelectedProfileId,
    selectedProfileChannels,
    channelsPageSelection,
  } = useChannelsStore();

  const {
    environment: { env_mode },
  } = useSettingsStore();

  const [channel, setChannel] = useState(null);
  const [channelModalOpen, setChannelModalOpen] = useState(false);
  const [recordingModalOpen, setRecordingModalOpen] = useState(false);
  const [rowSelection, setRowSelection] = useState([]);
  const [channelGroupOptions, setChannelGroupOptions] = useState([]);
  const [selectedProfile, setSelectedProfile] = useState(
    profiles[selectedProfileId]
  );
  const [channelsEnabledHeaderSwitch, setChannelsEnabledHeaderSwitch] =
    useState(false);

  const [hdhrUrl, setHDHRUrl] = useState(hdhrUrlBase);
  const [epgUrl, setEPGUrl] = useState(epgUrlBase);
  const [m3uUrl, setM3UUrl] = useState(m3uUrlBase);

  const [textToCopy, setTextToCopy] = useState('');

  const [filterValues, setFilterValues] = useState({});

  // const theme = useTheme();
  const theme = useMantineTheme();

  const { showVideo } = useVideoStore();

  useEffect(() => {
    setSelectedProfile(profiles[selectedProfileId]);

    const profileString =
      selectedProfileId != '0' ? `/${profiles[selectedProfileId].name}` : '';
    setHDHRUrl(`${hdhrUrlBase}${profileString}`);
    setEPGUrl(`${epgUrlBase}${profileString}`);
    setM3UUrl(`${m3uUrlBase}${profileString}`);
  }, [selectedProfileId]);

  useEffect(() => {
    setChannelGroupOptions([
      ...new Set(
        Object.values(channels).map((channel) => channel.channel_group?.name)
      ),
    ]);
  }, [channels]);

  const handleFilterChange = (columnId, value) => {
    setFilterValues((prev) => ({
      ...prev,
      [columnId]: Array.isArray(value)
        ? value
        : value
          ? value.toLowerCase()
          : '',
    }));
  };

  const hdhrUrlRef = useRef(null);
  const m3uUrlRef = useRef(null);
  const epgUrlRef = useRef(null);

  const toggleChannelEnabled = async (channelIds, enabled) => {
    if (channelIds.length == 1) {
      await API.updateProfileChannel(channelIds[0], selectedProfileId, enabled);
    } else {
      await API.updateProfileChannels(channelIds, selectedProfileId, enabled);
      setChannelsEnabledHeaderSwitch(enabled);
    }
  };

  // Configure columns
  const columns = useMemo(
    () => [
      {
        id: 'enabled',
        Header: () => {
          if (Object.values(rowSelection).length == 0) {
            return <ScanEye size="16" style={{ marginRight: 8 }} />;
          }

          return (
            <Switch
              size="xs"
              checked={selectedProfileId == '0' || channelsEnabledHeaderSwitch}
              onChange={() => {
                console.log(channelsPageSelection);
                toggleChannelEnabled(
                  channelsPageSelection.map((row) => row.id),
                  !channelsEnabledHeaderSwitch
                );
              }}
              disabled={selectedProfileId == '0'}
            />
          );
        },
        enableSorting: false,
        accessorFn: (row) => {
          if (selectedProfileId == '0') {
            return true;
          }

          return selectedProfileChannels.find((channel) => row.id == channel.id)
            .enabled;
        },
        mantineTableHeadCellProps: {
          align: 'right',
          style: {
            backgroundColor: '#3F3F46',
            width: '40px',
            minWidth: '40px',
            maxWidth: '40px',
            //   // minWidth: '20px',
            //   // width: '50px !important',
            //   // justifyContent: 'center',
            padding: 0,
            //   // paddingLeft: 8,
            //   // paddingRight: 0,
          },
        },
        mantineTableBodyCellProps: {
          align: 'right',
          style: {
            width: '40px',
            minWidth: '40px',
            maxWidth: '40px',
            //   // minWidth: '20px',
            //   // justifyContent: 'center',
            //   // paddingLeft: 0,
            //   // paddingRight: 0,
            padding: 0,
          },
        },
        Cell: ({ row, cell }) => (
          <Switch
            size="xs"
            checked={cell.getValue()}
            onChange={() => {
              toggleChannelEnabled([row.original.id], !cell.getValue());
            }}
            disabled={selectedProfileId == '0'}
          />
        ),
      },
      {
        header: '#',
        size: 50,
        maxSize: 50,
        accessorKey: 'channel_number',
        sortingFn: (a, b, columnId) => {
          return (
            parseInt(a.original.channel_number) -
            parseInt(b.original.channel_number)
          );
        },
        mantineTableHeadCellProps: {
          align: 'right',
          //   //   style: {
          //   //     backgroundColor: '#3F3F46',
          //   //     // minWidth: '20px',
          //   //     // justifyContent: 'center',
          //   //     // paddingLeft: 15,
          //   //     paddingRight: 0,
          //   //   },
        },
        mantineTableBodyCellProps: {
          align: 'right',
          //   //   style: {
          //   //     minWidth: '20px',
          //   //     // justifyContent: 'center',
          //   //     paddingLeft: 0,
          //   //     paddingRight: 0,
          //   //   },
        },
      },
      {
        header: 'Name',
        accessorKey: 'name',
        Header: ({ column }) => (
          <TextInput
            name="name"
            placeholder="Name"
            value={filterValues[column.id]}
            onChange={(e) => {
              e.stopPropagation();
              handleFilterChange(column.id, e.target.value);
            }}
            size="xs"
            variant="unstyled"
            className="table-input-header"
            onClick={(e) => e.stopPropagation()}
          />
        ),
        Cell: ({ cell }) => (
          <div
            style={{
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {cell.getValue()}
          </div>
        ),
      },
      {
        header: 'Group',
        accessorKey: 'channel_group.name',
        accessorFn: (row) => row.channel_group?.name || '',
        Cell: ({ cell }) => (
          <div
            style={{
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {cell.getValue()}
          </div>
        ),
        Header: ({ column }) => (
          <Box onClick={(e) => e.stopPropagation()}>
            <MultiSelect
              placeholder="Group"
              searchable
              size="xs"
              nothingFoundMessage="No options"
              onChange={(value) => {
                handleFilterChange(column.id, value);
              }}
              data={channelGroupOptions}
              variant="unstyled"
              className="table-input-header custom-multiselect"
            />
          </Box>
        ),
      },
      {
        header: '',
        accessorKey: 'logo',
        enableSorting: false,
        size: 75,
        mantineTableBodyCellProps: {
          align: 'center',
          style: {
            maxWidth: '75px',
          },
        },
        Cell: ({ cell }) => (
          <Grid
            direction="row"
            sx={{
              justifyContent: 'center',
              alignItems: 'center',
            }}
          >
            <img
              src={cell.getValue() ? cell.getValue().cache_url : logo}
              alt="channel logo"
              style={{
                width: 'auto',
                height: 'auto',
                maxWidth: '55px',
                maxHeight: '18px',
              }}
            />
          </Grid>
        ),
      },
    ],
    [
      channelGroupOptions,
      filterValues,
      selectedProfile,
      selectedProfileChannels,
      rowSelection,
      channelsPageSelection,
      channelsEnabledHeaderSwitch,
    ]
  );

  // Access the row virtualizer instance (optional)
  const rowVirtualizerInstanceRef = useRef(null);

  const [isLoading, setIsLoading] = useState(true);
  const [sorting, setSorting] = useState([
    { id: 'channel_number', desc: false },
    { id: 'name', desc: false },
  ]);

  const editChannel = async (ch = null) => {
    setChannel(ch);
    setChannelModalOpen(true);
  };

  const deleteChannel = async (id) => {
    setRowSelection([]);
    if (channelsPageSelection.length > 0) {
      return deleteChannels();
    }
    await API.deleteChannel(id);
  };

  const createRecording = (channel) => {
    setChannel(channel);
    setRecordingModalOpen(true);
  };

  function handleWatchStream(channelNumber) {
    let vidUrl = `/proxy/ts/stream/${channelNumber}`;
    if (env_mode == 'dev') {
      vidUrl = `${window.location.protocol}//${window.location.hostname}:5656${vidUrl}`;
    }
    showVideo(vidUrl);
  }

  // (Optional) bulk delete, but your endpoint is @TODO
  const deleteChannels = async () => {
    setIsLoading(true);
    const selected = table
      .getRowModel()
      .rows.filter((row) => row.getIsSelected());

    await API.deleteChannels(selected.map((row) => row.original.id));
    setIsLoading(false);
  };

  // ─────────────────────────────────────────────────────────
  // The "Assign Channels" button logic
  // ─────────────────────────────────────────────────────────
  const assignChannels = async () => {
    try {
      // Get row order from the table
      const rowOrder = table.getRowModel().rows.map((row) => row.original.id);

      // Call our custom API endpoint
      setIsLoading(true);
      const result = await API.assignChannelNumbers(rowOrder);
      setIsLoading(false);

      // We might get { message: "Channels have been auto-assigned!" }
      notifications.show({
        title: result.message || 'Channels assigned',
        color: 'green.5',
      });

      // Refresh the channel list
      await fetchChannels();
    } catch (err) {
      console.error(err);
      notifications.show({
        title: 'Failed to assign channels',
        color: 'red.5',
      });
    }
  };

  const matchEpg = async () => {
    try {
      // Hit our new endpoint that triggers the fuzzy matching Celery task
      await API.matchEpg();

      notifications.show({
        title: 'EPG matching task started!',
        // style: { width: '200px', left: '200px' },
      });
    } catch (err) {
      notifications.show(`Error: ${err.message}`);
    }
  };

  const closeChannelForm = () => {
    setChannel(null);
    setChannelModalOpen(false);
  };

  const closeRecordingForm = () => {
    // setChannel(null);
    setRecordingModalOpen(false);
  };

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Scroll to the top of the table when sorting changes
    try {
      rowVirtualizerInstanceRef.current?.scrollToIndex?.(0);
    } catch (error) {
      console.error(error);
    }
  }, [sorting]);

  const handleCopy = async (textToCopy, ref) => {
    try {
      await navigator.clipboard.writeText(textToCopy);
      notifications.show({
        title: 'Copied!',
        // style: { width: '200px', left: '200px' },
      });
    } catch (err) {
      const inputElement = ref.current; // Get the actual input

      if (inputElement) {
        inputElement.focus();
        inputElement.select();

        // For older browsers
        document.execCommand('copy');
        notifications.show({ title: 'Copied!' });
      }
    }
  };

  // Example copy URLs
  const copyM3UUrl = () => {
    handleCopy(m3uUrl, m3uUrlRef);
  };
  const copyEPGUrl = () => {
    handleCopy(epgUrl, epgUrlRef);
  };
  const copyHDHRUrl = () => {
    handleCopy(hdhrUrl, hdhrUrlRef);
  };

  useEffect(() => {
    const selectedRows = table
      .getSelectedRowModel()
      .rows.map((row) => row.original);
    setChannelsPageSelection(selectedRows);

    if (selectedProfileId != '0') {
      setChannelsEnabledHeaderSwitch(
        selectedRows.filter(
          (row) =>
            selectedProfileChannels.find((channel) => row.id == channel.id)
              .enabled
        ).length == selectedRows.length
      );
    }
  }, [rowSelection]);

  const filteredData = Object.values(channels).filter((row) =>
    columns.every(({ accessorKey }) => {
      if (!accessorKey) {
        return true;
      }

      const filterValue = filterValues[accessorKey];
      const rowValue = getDescendantProp(row, accessorKey);

      if (Array.isArray(filterValue) && filterValue.length != 0) {
        return filterValue.includes(rowValue);
      } else if (filterValue) {
        return rowValue?.toLowerCase().includes(filterValues[accessorKey]);
      }

      return true;
    })
  );

  const deleteProfile = async (id) => {
    await API.deleteChannelProfile(id);
  };

  const renderProfileOption = ({ option, checked }) => {
    return (
      <Group justify="space-between" style={{ width: '100%' }}>
        <Box>{option.label}</Box>
        {option.value != '0' && (
          <ActionIcon
            size="xs"
            variant="transparent"
            color={theme.tailwind.red[6]}
            onClick={(e) => {
              e.stopPropagation();
              deleteProfile(option.value);
            }}
          >
            <SquareMinus />
          </ActionIcon>
        )}
      </Group>
    );
  };

  const table = useMantineReactTable({
    ...TableHelper.defaultProperties,
    columns,
    data: filteredData,
    enablePagination: false,
    enableColumnActions: false,
    enableRowVirtualization: true,
    enableRowSelection: true,
    renderTopToolbar: false,
    onRowSelectionChange: setRowSelection,
    onSortingChange: setSorting,
    state: {
      isLoading: isLoading || channelsLoading,
      sorting,
      rowSelection,
    },
    rowVirtualizerInstanceRef,
    rowVirtualizerOptions: { overscan: 5 },
    initialState: {
      density: 'compact',
      sorting: [
        {
          id: 'channel_number',
          desc: false,
        },
      ],
    },
    enableRowActions: true,
    enableExpandAll: false,
    displayColumnDefOptions: {
      'mrt-row-select': {
        size: 10,
        maxSize: 10,
        mantineTableHeadCellProps: {
          align: 'right',
          style: {
            paddding: 0,
            // paddingLeft: 7,
            width: '20px',
            minWidth: '20px',
            backgroundColor: '#3F3F46',
          },
        },
        mantineTableBodyCellProps: {
          align: 'right',
          style: {
            paddingLeft: 0,
            width: '20px',
            minWidth: '20px',
          },
        },
      },
      'mrt-row-expand': {
        size: 20,
        maxSize: 20,
        header: '',
        mantineTableHeadCellProps: {
          style: {
            padding: 0,
            paddingLeft: 2,
            width: '20px',
            minWidth: '20px',
            maxWidth: '20px',
            backgroundColor: '#3F3F46',
          },
        },
        mantineTableBodyCellProps: {
          style: {
            padding: 0,
            paddingLeft: 2,
            width: '20px',
            minWidth: '20px',
            maxWidth: '20px',
          },
        },
      },
      'mrt-row-actions': {
        size: 85,
        maxWidth: 85,
        mantineTableHeadCellProps: {
          align: 'center',
          style: {
            minWidth: '85px',
            maxWidth: '85px',
            paddingRight: 40,
            fontWeight: 'normal',
            color: 'rgb(207,207,207)',
            backgroundColor: '#3F3F46',
          },
        },
        mantineTableBodyCellProps: {
          style: {
            minWidth: '85px',
            maxWidth: '85px',
            paddingLeft: 0,
            paddingRight: 10,
          },
        },
      },
    },
    mantineExpandButtonProps: ({ row, table }) => ({
      onClick: () => {
        setRowSelection({ [row.index]: true });
        table.setExpanded({ [row.id]: !row.getIsExpanded() });
      },
      size: 'xs',
      style: {
        transform: row.getIsExpanded() ? 'rotate(180deg)' : 'rotate(-90deg)',
        transition: 'transform 0.2s',
      },
    }),
    renderDetailPanel: ({ row }) => (
      <ChannelStreams channel={row.original} isExpanded={row.getIsExpanded()} />
    ),
    renderRowActions: ({ row }) => (
      <Box style={{ width: '100%', justifyContent: 'left' }}>
        <Center>
          <Tooltip label="Edit Channel">
            <ActionIcon
              size="xs"
              variant="transparent"
              color={theme.tailwind.yellow[3]}
              onClick={() => {
                editChannel(row.original);
              }}
            >
              <SquarePen size="18" />
            </ActionIcon>
          </Tooltip>

          <Tooltip label="Delete Channel">
            <ActionIcon
              size="xs"
              variant="transparent"
              color={theme.tailwind.red[6]}
              onClick={() => deleteChannel(row.original.id)}
              disabled={
                channelsPageSelection.length > 0 &&
                !channelsPageSelection
                  .map((row) => row.id)
                  .includes(row.original.id)
              }
            >
              {channelsPageSelection.length === 0 ? (
                <SquareMinus size="18" />
              ) : (
                <CopyMinus size="18" />
              )}
            </ActionIcon>
          </Tooltip>

          <Tooltip label="Preview Channel">
            <ActionIcon
              size="xs"
              variant="transparent"
              color={theme.tailwind.green[5]}
              onClick={() => handleWatchStream(row.original.uuid)}
            >
              <CirclePlay size="18" />
            </ActionIcon>
          </Tooltip>

          {env_mode == 'dev' && (
            <Menu>
              <Menu.Target>
                <ActionIcon variant="transparent" size="sm">
                  <EllipsisVertical size="18" />
                </ActionIcon>
              </Menu.Target>

              <Menu.Dropdown>
                <Menu.Item
                  onClick={() => createRecording(row.original)}
                  leftSection={
                    <div
                      style={{
                        borderRadius: '50%',
                        width: '10px',
                        height: '10px',
                        display: 'flex',
                        backgroundColor: 'red',
                      }}
                    ></div>
                  }
                >
                  Record
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          )}
        </Center>
      </Box>
    ),
    mantineTableContainerProps: {
      style: {
        height: 'calc(100vh - 110px)',
        overflowY: 'auto',
        // margin: 5,
      },
    },
  });

  return (
    <Box>
      {/* Header Row: outside the Paper */}
      <Flex
        style={{ display: 'flex', alignItems: 'center', paddingBottom: 10 }}
        gap={15}
      >
        <Text
          w={88}
          h={24}
          style={{
            fontFamily: 'Inter, sans-serif',
            fontWeight: 500,
            fontSize: '20px',
            lineHeight: 1,
            letterSpacing: '-0.3px',
            color: 'gray.6', // Adjust this to match MUI's theme.palette.text.secondary
            marginBottom: 0,
          }}
        >
          Channels
        </Text>
        <Flex
          style={{
            display: 'flex',
            alignItems: 'center',
            marginLeft: 10,
          }}
        >
          <Text
            w={37}
            h={17}
            style={{
              fontFamily: 'Inter, sans-serif',
              fontWeight: 400,
              fontSize: '14px',
              lineHeight: 1,
              letterSpacing: '-0.3px',
              color: 'gray.6', // Adjust this to match MUI's theme.palette.text.secondary
            }}
          >
            Links:
          </Text>

          <Group gap={5} style={{ paddingLeft: 10 }}>
            <Popover withArrow shadow="md">
              <Popover.Target>
                <Button
                  leftSection={<Tv2 size={18} />}
                  size="compact-sm"
                  p={5}
                  color="green"
                  variant="subtle"
                  style={{
                    borderColor: theme.palette.custom.greenMain,
                    color: theme.palette.custom.greenMain,
                  }}
                >
                  HDHR
                </Button>
              </Popover.Target>
              <Popover.Dropdown>
                <Group>
                  <TextInput ref={hdhrUrlRef} value={hdhrUrl} size="small" />
                  <ActionIcon
                    onClick={copyHDHRUrl}
                    size="sm"
                    variant="transparent"
                    color="gray.5"
                  >
                    <Copy size="18" fontSize="small" />
                  </ActionIcon>
                </Group>
              </Popover.Dropdown>
            </Popover>

            <Popover withArrow shadow="md">
              <Popover.Target>
                <Button
                  leftSection={<ScreenShare size={18} />}
                  size="compact-sm"
                  p={5}
                  variant="subtle"
                  style={{
                    borderColor: theme.palette.custom.indigoMain,
                    color: theme.palette.custom.indigoMain,
                  }}
                >
                  M3U
                </Button>
              </Popover.Target>
              <Popover.Dropdown>
                <Group>
                  <TextInput ref={m3uUrlRef} value={m3uUrl} size="small" />
                  <ActionIcon
                    onClick={copyM3UUrl}
                    size="sm"
                    variant="transparent"
                    color="gray.5"
                  >
                    <Copy size="18" fontSize="small" />
                  </ActionIcon>
                </Group>
              </Popover.Dropdown>
            </Popover>

            <Popover withArrow shadow="md">
              <Popover.Target>
                <Button
                  leftSection={<Scroll size={18} />}
                  size="compact-sm"
                  p={5}
                  variant="subtle"
                  color="gray.5"
                  style={{
                    borderColor: theme.palette.custom.greyBorder,
                    color: theme.palette.custom.greyBorder,
                  }}
                >
                  EPG
                </Button>
              </Popover.Target>
              <Popover.Dropdown>
                <Group>
                  <TextInput ref={epgUrlRef} value={epgUrl} size="small" />
                  <ActionIcon
                    onClick={copyEPGUrl}
                    size="sm"
                    variant="transparent"
                    color="gray.5"
                  >
                    <Copy size="18" fontSize="small" />
                  </ActionIcon>
                </Group>
              </Popover.Dropdown>
            </Popover>
          </Group>
        </Flex>
      </Flex>

      {/* Paper container: contains top toolbar and table (or ghost state) */}
      <Paper
        style={{
          height: 'calc(100vh - 60px)',
          backgroundColor: '#27272A',
        }}
      >
        {/* Top toolbar with Remove, Assign, Auto-match, and Add buttons */}
        <Group justify="space-between">
          <Group gap={5} style={{ paddingLeft: 10 }}>
            <Select
              size="xs"
              value={selectedProfileId}
              onChange={setSelectedProfileId}
              data={Object.values(profiles).map((profile) => ({
                label: profile.name,
                value: `${profile.id}`,
              }))}
              renderOption={renderProfileOption}
            />

            <Tooltip label="Create Profile">
              <CreateProfilePopover />
            </Tooltip>
          </Group>

          <Box
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              padding: 10,
            }}
          >
            <Flex gap={6}>
              <Button
                leftSection={<SquareMinus size={18} />}
                variant="default"
                size="xs"
                onClick={deleteChannels}
                disabled={Object.values(rowSelection).length == 0}
              >
                Remove
              </Button>

              <Tooltip label="Assign Channel #s">
                <Button
                  leftSection={<ArrowDown01 size={18} />}
                  variant="default"
                  size="xs"
                  onClick={assignChannels}
                  p={5}
                >
                  Assign
                </Button>
              </Tooltip>

              <Tooltip label="Auto-Match EPG">
                <Button
                  leftSection={<Binary size={18} />}
                  variant="default"
                  size="xs"
                  onClick={matchEpg}
                  p={5}
                >
                  Auto-Match
                </Button>
              </Tooltip>

              <Button
                leftSection={<SquarePlus size={18} />}
                variant="light"
                size="xs"
                onClick={() => editChannel()}
                p={5}
                color={theme.tailwind.green[5]}
                style={{
                  borderWidth: '1px',
                  borderColor: theme.tailwind.green[5],
                  color: 'white',
                }}
              >
                Add
              </Button>
            </Flex>
          </Box>
        </Group>

        {/* Table or ghost empty state inside Paper */}
        <Box>
          {Object.keys(channels).length === 0 && (
            <Box
              style={{
                paddingTop: 20,
                bgcolor: theme.palette.background.paper,
              }}
            >
              <Center>
                <Box
                  style={{
                    textAlign: 'center',
                    width: '55%',
                  }}
                >
                  <Text
                    style={{
                      fontFamily: 'Inter, sans-serif',
                      fontWeight: 400,
                      fontSize: '20px',
                      lineHeight: '28px',
                      letterSpacing: '-0.3px',
                      color: theme.palette.text.secondary,
                      mb: 1,
                    }}
                  >
                    It’s recommended to create channels after adding your M3U or
                    streams.
                  </Text>
                  <Text
                    style={{
                      fontFamily: 'Inter, sans-serif',
                      fontWeight: 400,
                      fontSize: '16px',
                      lineHeight: '24px',
                      letterSpacing: '-0.2px',
                      color: theme.palette.text.secondary,
                      mb: 2,
                    }}
                  >
                    You can still create channels without streams if you’d like,
                    and map them later.
                  </Text>
                  <Button
                    leftSection={<SquarePlus size={18} />}
                    variant="light"
                    size="xs"
                    onClick={() => editChannel()}
                    color="gray"
                    style={{
                      marginTop: 20,
                      borderWidth: '1px',
                      borderColor: 'gray',
                      color: 'white',
                    }}
                  >
                    Create Channel
                  </Button>
                </Box>
              </Center>

              <Center>
                <Box
                  component="img"
                  src={ghostImage}
                  alt="Ghost"
                  style={{
                    paddingTop: 30,
                    width: '120px',
                    height: 'auto',
                    opacity: 0.2,
                    pointerEvents: 'none',
                  }}
                />
              </Center>
            </Box>
          )}
        </Box>
        {Object.keys(channels).length > 0 && (
          <MantineReactTable table={table} />
        )}
      </Paper>

      <ChannelForm
        channel={channel}
        isOpen={channelModalOpen}
        onClose={closeChannelForm}
      />

      <RecordingForm
        channel={channel}
        isOpen={recordingModalOpen}
        onClose={closeRecordingForm}
      />
    </Box>
  );
};

export default ChannelsTable;
