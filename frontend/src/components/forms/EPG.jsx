// Modal.js
import React, { useState, useEffect } from 'react';
import API from '../../api';
import useEPGsStore from '../../store/epgs';
import {
  LoadingOverlay,
  TextInput,
  Button,
  Checkbox,
  Modal,
  Flex,
  NativeSelect,
  NumberInput,
  Space,
} from '@mantine/core';
import { isNotEmpty, useForm } from '@mantine/form';

const EPG = ({ epg = null, isOpen, onClose }) => {
  const epgs = useEPGsStore((state) => state.epgs);
  const [file, setFile] = useState(null);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setFile(file);
    }
  };

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: {
      name: '',
      source_type: 'xmltv',
      url: '',
      api_key: '',
      is_active: true,
      refresh_interval: 24,
    },

    validate: {
      name: isNotEmpty('Please select a name'),
      source_type: isNotEmpty('Source type cannot be empty'),
    },
  });

  const onSubmit = async () => {
    const values = form.getValues();

    if (epg?.id) {
      await API.updateEPG({ id: epg.id, ...values, file });
    } else {
      await API.addEPG({
        ...values,
        file,
      });
    }

    form.reset();
    setFile(null);
    onClose();
  };

  useEffect(() => {
    if (epg) {
      form.setValues({
        name: epg.name,
        source_type: epg.source_type,
        url: epg.url,
        api_key: epg.api_key,
        is_active: epg.is_active,
        refresh_interval: epg.refresh_interval,
      });
    } else {
      form.reset();
    }
  }, [epg]);

  if (!isOpen) {
    return <></>;
  }

  return (
    <Modal opened={isOpen} onClose={onClose} title="EPG Source">
      <form onSubmit={form.onSubmit(onSubmit)}>
        <TextInput
          id="name"
          name="name"
          label="Name"
          {...form.getInputProps('name')}
          key={form.key('name')}
        />

        <TextInput
          id="url"
          name="url"
          label="URL"
          {...form.getInputProps('url')}
          key={form.key('url')}
        />

        <TextInput
          id="api_key"
          name="api_key"
          label="API Key"
          {...form.getInputProps('api_key')}
          key={form.key('api_key')}
        />

        <NativeSelect
          id="source_type"
          name="source_type"
          label="Source Type"
          {...form.getInputProps('source_type')}
          key={form.key('source_type')}
          data={[
            {
              label: 'XMLTV',
              value: 'xmltv',
            },
            {
              label: 'Schedules Direct',
              value: 'schedules_direct',
            },
          ]}
        />

        <NumberInput
          label="Refresh Interval (hours)"
          {...form.getInputProps('refresh_interval')}
          key={form.key('refresh_interval')}
        />

        <Flex mih={50} gap="xs" justify="flex-end" align="flex-end">
          <Button
            type="submit"
            variant="contained"
            disabled={form.submiting}
            size="small"
          >
            Submit
          </Button>
        </Flex>
      </form>
    </Modal>
  );
};

export default EPG;
