extern "C" float sqrtf(float);
extern "C" float atan2f(float, float);

extern unsigned char dmaBuff0[0x100];
extern unsigned char dmaBuff1[0x100];

class ccPad
{
public:
    unsigned char* dmaBuffer;      // 0x00
    int padState;                  // 0x04

    unsigned char padData[0x20];   // 0x08 - 0x27
    unsigned char actuator[6];     // 0x28 - 0x2D
    unsigned char field_2E;        // 0x2E
    unsigned char field_2F;        // 0x2F

    unsigned char field_30[0x10];  // 0x30 - 0x3F

    unsigned char field_40;        // 0x40
    unsigned char field_41;        // 0x41
    unsigned char field_42;        // 0x42
    unsigned char field_43;        // 0x43
    unsigned char field_44;        // 0x44
    unsigned char field_45;        // 0x45

    unsigned char port;            // 0x46
    unsigned char slot;            // 0x47

    unsigned char analogMag0;      // 0x48
    unsigned char analogMag1;      // 0x49
    unsigned char pad_4A[2];       // 0x4A - 0x4B

    float analogAngle0;            // 0x4C
    float analogAngle1;            // 0x50

    unsigned char field_54[0x10];  // 0x54 - 0x63

    unsigned int field_64;         // 0x64
    unsigned int field_68;         // 0x68
    unsigned int field_6C;         // 0x6C
    unsigned int field_70;         // 0x70

    void Init(unsigned char port, unsigned char slot);
};

typedef char ccPad_size_check[(sizeof(ccPad) == 0x74) ? 1 : -1];

void ccPad::Init(unsigned char padPort, unsigned char padSlot)
{
    if (padPort) {
        dmaBuffer = dmaBuff1;
    } else {
        dmaBuffer = dmaBuff0;
    }

    field_64 = 0;
    field_70 = 0;
    field_6C = 0;
    field_68 = 0;

    analogAngle1 = 0.0f;
    analogAngle0 = 0.0f;

    analogMag1 = 0;
    analogMag0 = 0;

    field_43 = 0;

    port = padPort;
    slot = padSlot;

    field_44 = 0;
}

int SetAnalogStick(float* angle, unsigned char* magnitude, int x, int y)
{
    int temp = x - 0x80;
    int adjusted_x;
    int adjusted_y;

    if (temp > 0x30) {
        adjusted_x = x - 0xB0;
    } else {
        adjusted_x = 0;

        if (temp < -0x30) {
            adjusted_x = x - 0x50;
        }
    }

    temp = y - 0x80;

    if (temp > 0x30) {
        adjusted_y = y - 0xB0;
    } else if (temp < -0x30) {
        adjusted_y = y - 0x50;
    } else {
        adjusted_y = 0;
    }

    int value = (int)(
        (255.0f *
         sqrtf((float)(
             adjusted_x * adjusted_x +
             adjusted_y * adjusted_y
         ))) /
        80.0f
    );

    if (value > 0xFF) {
        value = 0xFF;
    }

    if (value != 0) {
        int centered_y = y - 0x80;

        if (centered_y != 0) {
            float result = atan2f(
                (float)-(x - 0x80),
                (float)centered_y
            );

            if (result < -3.1415927f) {
                result = 6.2831855f + result;
            }

            *angle = result;
        } else {
            *angle = 0.0f;
        }

        *magnitude = (unsigned char)value;

        return 0;
    }

    *angle = 0.0f;
    *magnitude = 0;

    return 1;
}
