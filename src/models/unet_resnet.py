import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import models


class ConvRelu(nn.Module):
    def __init__(self, in_, out):
        super().__init__()
        self.layer = nn.Sequential(
            nn.Conv2d(in_, out, 3, padding=1), nn.ReLU(inplace=True)
        )

    def forward(self, x):
        return self.layer(x)


class UNetResNet(nn.Module):
    def __init__(
        self,
        encoder_depth,
        num_classes,
        num_filters=32,
        dropout_2d=0.2,
        pretrained=False,
        is_deconv=False,
    ):
        super().__init__()
        self.num_classes = num_classes
        self.dropout_2d = dropout_2d

        if encoder_depth == 34:
            self.encoder = models.resnet34(pretrained=pretrained)
            bottom_channel_nr = 512
        elif encoder_depth == 101:
            self.encoder = models.resnet101(pretrained=pretrained)
            bottom_channel_nr = 2048
        elif encoder_depth == 152:
            self.encoder = models.resnet152(pretrained=pretrained)
            bottom_channel_nr = 2048

        else:
            raise NotImplementedError(
                "only 34, 101, 152 version of Resnet are implemented"
            )

        self.pool = nn.MaxPool2d(2, 2)
        self.relu = nn.ReLU(inplace=True)
        self.conv1 = nn.Sequential(
            self.encoder.conv1, self.encoder.bn1, self.encoder.relu, self.pool
        )  # from that pool layer I would like to get rid off

        self.conv2 = self.encoder.layer1
        self.conv3 = self.encoder.layer2
        self.conv4 = self.encoder.layer3
        self.conv5 = self.encoder.layer4
        self.center = DecoderCenter(
            bottom_channel_nr, num_filters * 8 * 2, num_filters * 8, False
        )
        self.dec5 = DecoderBlockV(
            bottom_channel_nr + num_filters * 8,
            num_filters * 8 * 2,
            num_filters * 8,
            is_deconv,
        )
        self.dec4 = DecoderBlockV(
            bottom_channel_nr // 2 + num_filters * 8,
            num_filters * 8 * 2,
            num_filters * 8,
            is_deconv,
        )
        self.dec3 = DecoderBlockV(
            bottom_channel_nr // 4 + num_filters * 8,
            num_filters * 4 * 2,
            num_filters * 2,
            is_deconv,
        )
        self.dec2 = DecoderBlockV(
            bottom_channel_nr // 8 + num_filters * 2,
            num_filters * 2 * 2,
            num_filters * 2 * 2,
            is_deconv,
        )
        self.dec1 = DecoderBlockV(
            num_filters * 2 * 2, num_filters * 2 * 2, num_filters, is_deconv
        )
        self.dec0 = ConvRelu(num_filters, num_filters)
        self.final = nn.Conv2d(num_filters, num_classes, kernel_size=1)

    def forward(self, x):
        conv1 = self.conv1(x)
        conv2 = self.conv2(conv1)
        conv3 = self.conv3(conv2)
        conv4 = self.conv4(conv3)
        conv5 = self.conv5(conv4)
        center = self.center(conv5)
        dec5 = self.dec5(torch.cat([center, conv5], 1))
        dec4 = self.dec4(torch.cat([dec5, conv4], 1))
        dec3 = self.dec3(torch.cat([dec4, conv3], 1))
        dec2 = self.dec2(torch.cat([dec3, conv2], 1))
        dec1 = self.dec1(dec2)
        dec0 = self.dec0(dec1)
        return self.final(F.dropout2d(dec0, p=self.dropout_2d))


class DecoderBlockV(nn.Module):
    def __init__(self, in_channels, middle_channels, out_channels, is_deconv=True):
        super(DecoderBlockV, self).__init__()
        self.in_channels = in_channels

        if is_deconv:
            self.block = nn.Sequential(
                ConvRelu(in_channels, middle_channels),
                nn.ConvTranspose2d(
                    middle_channels, out_channels, kernel_size=4, stride=2, padding=1
                ),
                nn.BatchNorm2d(out_channels),
                nn.ReLU(inplace=True),
            )
        else:
            self.block = nn.Sequential(
                nn.Upsample(scale_factor=2, mode="bilinear"),
                ConvRelu(in_channels, middle_channels),
                ConvRelu(middle_channels, out_channels),
            )

    def forward(self, x):
        return self.block(x)


class DecoderCenter(nn.Module):
    def __init__(self, in_channels, middle_channels, out_channels, is_deconv=True):
        super(DecoderCenter, self).__init__()
        self.in_channels = in_channels

        if is_deconv:
            """
                Paramaters for Deconvolution were chosen to avoid artifacts, following
                link https://distill.pub/2016/deconv-checkerboard/
            """

            self.block = nn.Sequential(
                ConvRelu(in_channels, middle_channels),
                nn.ConvTranspose2d(
                    middle_channels, out_channels, kernel_size=4, stride=2, padding=1
                ),
                nn.BatchNorm2d(out_channels),
                nn.ReLU(inplace=True),
            )
        else:
            self.block = nn.Sequential(
                ConvRelu(in_channels, middle_channels),
                ConvRelu(middle_channels, out_channels),
            )

    def forward(self, x):
        return self.block(x)


__all__ = ["UNetResNet"]
