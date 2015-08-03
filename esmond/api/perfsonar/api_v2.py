import calendar
import collections
import copy
import datetime
import inspect
import json
import time
import urlparse

import pprint

pp = pprint.PrettyPrinter(indent=4)

from rest_framework import (viewsets, serializers, status, 
        fields, relations, pagination, mixins, throttling)
from rest_framework.exceptions import (ParseError, NotFound, APIException)
from rest_framework.response import Response
from rest_framework.reverse import reverse

import rest_framework_filters as filters

from esmond.api.models import (PSMetadata, PSPointToPointSubject, PSEventTypes, 
    PSMetadataParameters, PSNetworkElementSubject)

from esmond.api.api_v2 import DataObject

#
# Bases, etc
#

class BaseMixin(object):
    def undash_dict(self, d):
        for i in d.keys():
            d[i.replace('-', '_')] = d.pop(i)

    def to_dash_dict(self, d):
        for i in d.keys():
            d[i.replace('_', '-')] = d.pop(i)

#
# Base /archive/ endpoint
#

class ArchiveDataObject(DataObject):
    pass

class ArchiveSerializer(BaseMixin, serializers.ModelSerializer):
    class Meta:
        model = PSMetadata
        fields = (
            'metadata_key', 
            'subject_type', 
            'destination',
            'source',
            'tool_name',
            'measurement_agent',
            'input_source',
            'input_destination',
            'event_types',
            )

    ## elements from PSPointToPointSubject
    # ips
    source = fields.IPAddressField(source='pspointtopointsubject.source')
    destination = fields.IPAddressField(source='pspointtopointsubject.destination')
    measurement_agent = fields.IPAddressField(source='pspointtopointsubject.measurement_agent')
    # char fields
    tool_name = fields.CharField(source='pspointtopointsubject.tool_name')
    input_source = fields.CharField(source='pspointtopointsubject.input_source')
    input_destination = fields.CharField(source='pspointtopointsubject.input_destination')
    ## elements from event type table - this is dynamically generated, 
    # so just use the type elements.
    event_types = fields.ListField(child=serializers.DictField())

    def to_representation(self, obj):
        """
        Generate event_types list.
        Modify outgoing data: massage underscore => dash.
        """

        # generate event type list for outgoing payload
        obj.event_types = list()
        for et in obj.pseventtypes.all():
            d = dict(
                    base_uri='MAKE URI HERE',
                    event_type=et.event_type,
                    time_updated=et.time_updated, # CONVERT TIME
                )
            self.to_dash_dict(d)
            obj.event_types.append(d)

        # serialize it now
        ret = super(ArchiveSerializer, self).to_representation(obj)

        # now add the arbitrary metadata values from the PSMetadataParameters
        # table.
        for p in obj.psmetadataparameters.all():
            ret[p.parameter_key] = p.parameter_value

        # convert underscores to dashes in attr names
        self.to_dash_dict(ret)
        return ret

    def to_internal_value(self, data):
        """
        Modify incoming json: massage dash => underscore before calling 
        base code. Probably irrelevant since input will be handled 
        by custom create methods.
        """
        # convert dashes to underscores before doing object
        # conversion.
        self.undash_dict(data)
        ret = super(ArchiveSerializer, self).to_internal_value(data)
        return ret

class ArchiveViewset(mixins.CreateModelMixin,
                    mixins.ListModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.UpdateModelMixin,
                    viewsets.GenericViewSet):

    """Implements GET, PUT and POST model operations w/specific mixins rather 
    than using viewsets.ModelSerializer for all the ops."""

    serializer_class = ArchiveSerializer
    lookup_field = 'metadata_key'

    def get_queryset(self):
        # Modify for custom filtering logic, etc
        ret = PSMetadata.objects.all()
        return ret

    def list(self, request):
        """Stub for list GET ie:

        GET /perfsonar/archive/"""
        return super(ArchiveViewset, self).list(request)

    def retrieve(self, request, **kwargs):
        """Stub for detail GET 'metadata_key', will be one of 
        the kwargs since that is defined as the lookup field for the 
        detail view - ie:

        /GET perfsonar/archive/$METADATA_KEY/
        """
        print self.kwargs
        instance = self.get_object()
        return super(ArchiveViewset, self).retrieve(request, **kwargs)

    def create(self, request):
        """Stub for POST metadata object creation - ie:

        POST /perfsonar/archive/"""
        print 'create'
        # validate the incoming json and data contained therein.
        if not request.content_type.startswith('application/json'):
            return Response({'error': 'Must post content-type: application/json header and json-formatted payload.'},
                status.HTTP_400_BAD_REQUEST)

        if not request.body:
            return Response({'error': 'No data payload POSTed.'}, status.HTTP_400_BAD_REQUEST)

        try:
            request_data = json.loads(request.body)
        except ValueError:
            return Response({'error': 'POST data payload could not be decoded to a JSON object - given: {0}'.format(request.body)},
                status.HTTP_400_BAD_REQUEST)

        # process the json blob that was sent to the server.
        # print request_data

        # assemble return payload and send back to the client, or 
        # empty string/etc.
        return_payload = dict(thanks='for that')
        return Response(return_payload, status.HTTP_201_CREATED)

    def update(self, request, **kwargs):
        """Stub for PUT detail object creation to a metadata instance 
        for bulk data/event type creation. ie:

        PUT /perfsonar/archive/$METADATA_KEY/

        'metadata_key' will be in kwargs
        """
        print 'update', kwargs
        # validate the incoming json and data contained therein.
        if not request.content_type.startswith('application/json'):
            return Response({'error': 'Must post content-type: application/json header and json-formatted payload.'},
                status.HTTP_400_BAD_REQUEST)

        if not request.body:
            return Response({'error': 'No data payload POSTed.'}, status.HTTP_400_BAD_REQUEST)

        try:
            request_data = json.loads(request.body)
        except ValueError:
            return Response({'error': 'POST data payload could not be decoded to a JSON object - given: {0}'.format(request.body)},
                status.HTTP_400_BAD_REQUEST)

        # process the json blob that was sent to the server.
        # print request_data

        # assemble return payload and send back to the client, or 
        # empty string/etc.
        return_payload = dict(thanks='for that')
        return Response(return_payload, status.HTTP_201_CREATED)

    def partial_update(self, request, **kwargs):
        return Response({'error': 'does not support PATCH verb'}, status.HTTP_400_BAD_REQUEST)




